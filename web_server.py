"""
web_server.py - 輕量化 Socket Web Server 模組 (取代 Microdot)
以 uasyncio / 原生 Socket 處理 HTTP 請求，提供與專案完全相同的 Web API 與前端靜態頁面。
大幅降低 MicroPython 在 ESP32 上的記憶體佔用。
"""

try:
    import network
except ImportError:
    network = None
try:
    import uasyncio
except ImportError:
    import asyncio as uasyncio
try:
    import ujson as json
except ImportError:
    import json
from hardware.rfid import new_rfid_state
from hardware.motion import new_motion_state
import config
# ==================== 輕量級 HTTP Request / Response ====================

class Request:
    """輕量化 HTTP Request 物件，相容 Microdot 屬性存取契約。"""
    def __init__(self, method='GET', path='/', headers=None, body=b''):
        self.method = method
        self.path = path
        self.headers = headers or {}
        self.body = body

    @property
    def json(self):
        if not self.body:
            return None
        if isinstance(self.body, dict):
            return self.body
        try:
            raw = self.body.decode('utf-8') if isinstance(self.body, (bytes, bytearray)) else self.body
            return json.loads(raw)
        except Exception:
            return None


class Response:
    """輕量化 HTTP Response 物件，支援字串、位元組與檔案流 (send_file)。"""
    def __init__(self, body='', status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.body = body
        self.reason = {
            200: 'OK', 202: 'Accepted', 400: 'Bad Request', 404: 'Not Found',
            409: 'Conflict', 429: 'Too Many Requests', 500: 'Internal Server Error',
            503: 'Service Unavailable'
        }.get(status_code, 'OK')
        self.is_head = False

    def complete(self):
        if 'Content-Type' not in self.headers:
            if isinstance(self.body, str):
                self.headers['Content-Type'] = 'text/html; charset=utf-8'
            elif isinstance(self.body, (bytes, bytearray)):
                self.headers['Content-Type'] = 'application/octet-stream'

    async def body_iter(self):
        """非同步迭代產生器，相容 TestClient 與串流傳輸。"""
        if isinstance(self.body, str):
            yield self.body.encode('utf-8')
        elif isinstance(self.body, (bytes, bytearray)):
            yield self.body
        elif hasattr(self.body, 'read'):
            try:
                while True:
                    chunk = self.body.read(1024)
                    if not chunk:
                        break
                    if isinstance(chunk, str):
                        chunk = chunk.encode('utf-8')
                    yield chunk
            finally:
                if hasattr(self.body, 'close'):
                    self.body.close()

    @classmethod
    def send_file(cls, filename, status_code=200, content_type=None, max_age=None):
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type
        if max_age is not None:
            headers['Cache-Control'] = f'max-age={max_age}'
        try:
            import os
            stat = os.stat(filename)
            headers['Content-Length'] = str(stat[6] if len(stat) > 6 else stat.st_size)
            f = open(filename, 'rb')
            return cls(body=f, status_code=status_code, headers=headers)
        except Exception:
            return cls('File not found', status_code=404)


# ==================== 輕量級 Socket 應用核心 ====================

class SocketApp:
    """極簡的非同步 Socket HTTP 路由器，替代記憶體佔用龐大的 Microdot。"""
    def __init__(self):
        self.routes = []

    def route(self, path, methods=None):
        methods = [m.upper() for m in methods] if methods else ['GET']
        def decorator(handler):
            self.routes.append((methods, path, handler))
            return handler
        return decorator

    async def dispatch_request(self, req):
        """派發 HTTP 請求至對應的路由處理常式。"""
        for methods, path_pattern, handler in self.routes:
            if req.method in methods:
                if '<int:command_id>' in path_pattern:
                    prefix = path_pattern.split('<int:command_id>')[0]
                    if req.path.startswith(prefix):
                        param = req.path[len(prefix):]
                        if param.isdigit():
                            return await handler(req, int(param))
                elif req.path == path_pattern:
                    return await handler(req)
        return Response('Not Found', status_code=404)

    async def _handle_client(self, reader, writer):
        """非同步讀取 Socket 請求、派發處理並回寫 HTTP 回應。"""
        try:
            line = await reader.readline()
            if not line:
                return
            parts = line.decode('utf-8').strip().split()
            if len(parts) < 2:
                return
            method = parts[0].upper()
            full_path = parts[1]
            path = full_path.split('?')[0]

            headers = {}
            content_length = 0
            while True:
                hline = await reader.readline()
                if not hline or hline in (b'\r\n', b'\n'):
                    break
                try:
                    hstr = hline.decode('utf-8').strip()
                    if ':' in hstr:
                        k, v = hstr.split(':', 1)
                        k_lower = k.strip().lower()
                        v_clean = v.strip()
                        headers[k_lower] = v_clean
                        if k_lower == 'content-length':
                            content_length = int(v_clean)
                except Exception:
                    pass

            body = b''
            if content_length > 0:
                if hasattr(reader, 'readexactly'):
                    body = await reader.readexactly(content_length)
                else:
                    body = await reader.read(content_length)

            req = Request(method=method, path=path, headers=headers, body=body)
            print(f"[Web] 請求: {method} {path}")
            res = await self.dispatch_request(req)
            if res is None:
                res = Response('Not Found', status_code=404)

            await self._write_response(writer, res)
            print(f"[Web] 回應完成: {method} {path} -> {res.status_code}")
        except Exception as e:
            print(f"[Web] 連線處理異常: {e}")
        finally:
            try:
                writer.close()
                if hasattr(writer, 'wait_closed'):
                    await writer.wait_closed()
            except Exception:
                pass

    async def _write_response(self, writer, res):
        """向 Socket 寫入 HTTP 狀態列、標頭與正文。"""
        res.complete()
        status_text = res.reason or 'OK'
        header_lines = [
            f"HTTP/1.1 {res.status_code} {status_text}\r\n",
            "Connection: close\r\n"
        ]

        body_bytes = None
        if isinstance(res.body, str):
            body_bytes = res.body.encode('utf-8')
        elif isinstance(res.body, (bytes, bytearray)):
            body_bytes = res.body

        if body_bytes is not None:
            res.headers['Content-Length'] = str(len(body_bytes))

        for k, v in res.headers.items():
            header_lines.append(f"{k}: {v}\r\n")
        header_lines.append("\r\n")

        writer.write("".join(header_lines).encode('utf-8'))
        if hasattr(writer, 'drain'):
            await writer.drain()

        if body_bytes is not None:
            chunk_size = 1024
            for i in range(0, len(body_bytes), chunk_size):
                writer.write(body_bytes[i:i + chunk_size])
                if hasattr(writer, 'drain'):
                    await writer.drain()
        elif hasattr(res.body, 'read'):
            f = res.body
            try:
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    if isinstance(chunk, str):
                        chunk = chunk.encode('utf-8')
                    writer.write(chunk)
                    if hasattr(writer, 'drain'):
                        await writer.drain()
            finally:
                if hasattr(f, 'close'):
                    f.close()

    async def start_server(self, host='0.0.0.0', port=80, debug=False):
        """啟動非同步 Socket 伺服器並持續監聽。"""
        server = await uasyncio.start_server(self._handle_client, host, port)
        if hasattr(server, 'wait_closed'):
            await server.wait_closed()
        else:
            while True:
                await uasyncio.sleep(3600)


# ==================== 全局變數 ====================

app = SocketApp()

# 由 main.py 設置的全局變數
mqtt_manager = None
publish_event = None
sensor_snapshot = None
command_service = None
led_controller = None
rfid_state = new_rfid_state()
motion_state = new_motion_state()

# HTML 頁面（從 index.html 導入）
HTML_PAGE = None

def load_html():
    """載入 HTML 頁面"""
    global HTML_PAGE
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            HTML_PAGE = f.read()
    except Exception as e:
        print(f"[Web] 讀取 index.html 失敗: {e}")
        HTML_PAGE = '<html><head><meta charset="utf-8"><title>IoT Web Server</title></head><body><h1>IoT Web Server</h1><p>❌ index.html 文件未找到</p><p>錯誤詳情: {}</p></body></html>'.format(str(e))


# ==================== 工具函數 ====================

def get_wifi_ip():
    """
    獲取 ESP32 的 WiFi IP 地址
    返回：IP 地址字串，若未連接則返回 None
    """
    if network is None:
        return None
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.active() and wlan.isconnected():
            return wlan.ifconfig()[0]
        else:
            return None
    except Exception as e:
        print(f"[Web] 獲取 IP 失敗: {e}")
        return None

def _sensor_field(name):
    if sensor_snapshot is None:
        return {'value': None, 'valid': False, 'quality': 'unavailable',
                'age_ms': None, 'error': 'snapshot_unavailable',
                'updated_at_ms': None}
    return sensor_snapshot.snapshot()[name]


def get_current_temperature():
    """Return the cached temperature; never trigger a DHT read."""
    return _sensor_field('temperature')['value']


def get_current_humidity():
    """Return the cached humidity; never trigger a DHT read."""
    return _sensor_field('humidity')['value']


def get_current_light():
    """Return the cached ADC value; never trigger an ADC read."""
    return _sensor_field('light')['value']


# ==================== Web 路由 ====================

@app.route('/')
async def index(request):
    """主頁面：返回 HTML UI"""
    print("[Web] GET / (主頁)")
    if HTML_PAGE is None:
        load_html()
    return Response(HTML_PAGE, headers={'Content-Type': 'text/html; charset=utf-8'})


@app.route('/index.html')
async def index_html(request):
    """/index.html 路由（備用）"""
    print("[Web] GET /index.html")
    if HTML_PAGE is None:
        load_html()
    return Response(HTML_PAGE, headers={'Content-Type': 'text/html; charset=utf-8'})

@app.route('/test')
async def test_page(request):
    """簡易測試頁面，確認 Socket Web Server 連線與回應正常。"""
    html = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>ESP32 Socket 測試</title></head>
<body style="font-family:sans-serif; text-align:center; padding:50px; background:#f4f6f9;">
    <h1 style="color:#2ecc71;">✅ ESP32 Socket Web Server 運行正常！</h1>
    <p style="color:#555; font-size:18px;">原生 Socket 網頁伺服器已成功連線並傳輸 HTML。</p>
    <hr style="margin:30px auto; max-width:400px; border:1px solid #ddd;">
    <p><a href="/" style="font-size:20px; color:#3498db; text-decoration:none; font-weight:bold;">👉 前往完整專題儀表板 (/)</a></p>
    <p><a href="/api/data" style="font-size:16px; color:#e67e22; text-decoration:none;">🔍 查看 JSON 資料 (/api/data)</a></p>
</body>
</html>"""
    return Response(html, headers={'Content-Type': 'text/html; charset=utf-8'})


@app.route('/assets/uplot/1.6.32/uPlot.iife.min.js')
async def uplot_javascript(request):
    """Serve the pinned local uPlot runtime without loading it into HTML_PAGE."""
    return Response.send_file(
        'assets/uplot/1.6.32/uPlot.iife.min.js',
        content_type='application/javascript; charset=utf-8',
        max_age=31536000)


@app.route('/assets/uplot/1.6.32/uPlot.min.css')
async def uplot_stylesheet(request):
    """Serve the pinned local uPlot stylesheet."""
    return Response.send_file(
        'assets/uplot/1.6.32/uPlot.min.css',
        content_type='text/css; charset=utf-8',
        max_age=31536000)


@app.route('/api/data')
async def api_data(request):
    """Return sensor and control snapshots without sampling hardware."""
    snapshot = sensor_snapshot.snapshot() if sensor_snapshot is not None else {
        'temperature': _sensor_field('temperature'),
        'humidity': _sensor_field('humidity'),
        'light': _sensor_field('light'),
        'sample_seq': 0,
        'status': 'unavailable',
    }
    temp = snapshot['temperature']['value']
    humidity = snapshot['humidity']['value']
    light = snapshot['light']['value']
    if temp is not None:
        temp = round(temp, 1)
    if humidity is not None:
        humidity = round(humidity, 1)
    response_json = json.dumps({
        'temp': temp,
        'humidity': humidity,
        'light': light,
        'sensor': snapshot,
        'light_thresholds': {
            'trigger': config.LIGHT_ALERT_TRIGGER_ADC,
            'reset': config.LIGHT_ALERT_RESET_ADC
        },
        'status': snapshot['status'],
        'rfid': dict(rfid_state),
        'motion': dict(motion_state),
        'led': command_service.snapshot() if command_service else {
            'available': False,
            'mode': 'unknown',
            'alert_active': False,
        }
    })
    return Response(response_json, headers={
        'Content-Type': 'application/json; charset=utf-8'})


@app.route('/api/motion/status')
async def api_motion_status(request):
    """快速回傳PIR／喇叭RAM快照，不讀取DHT、ADC或SPI。"""
    return Response(json.dumps(dict(motion_state)), headers={
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store'})


def _command_response(receipt):
    status = 202 if receipt['status'] == 'accepted' else {
        'busy': 409,
        'manual_mode': 409,
        'queue_full': 429,
        'stopped': 503,
        'invalid_command': 400,
        'invalid_color': 400,
        'invalid_mode': 400,
        'invalid_source': 400,
        'unavailable': 503,
    }.get(receipt.get('reason'), 400)
    return Response(
        json.dumps(receipt),
        status_code=status,
        headers={'Content-Type': 'application/json; charset=utf-8'})


@app.route('/api/led/toggle', methods=['POST'])
async def api_led_toggle(request):
    """Submit a cycle command through CommandService."""
    print("[Web] POST /api/led/toggle")
    if command_service is None:
        return _command_response({
            'status': 'rejected',
            'reason': 'unavailable',
        })
    return _command_response(command_service.submit('cycle', 'web'))


@app.route('/api/led/commands', methods=['POST'])
async def api_led_command(request):
    """Submit a canonical Web LED command through CommandService."""
    payload = request.json if request is not None else None
    payload = payload if isinstance(payload, dict) else {}
    if command_service is None:
        return _command_response({
            'status': 'rejected',
            'reason': 'unavailable',
        })
    return _command_response(command_service.submit(
        payload.get('kind'), 'web', payload.get('value')))


@app.route('/api/led/mode', methods=['POST'])
async def api_led_mode(request):
    """Change AUTO／MANUAL mode through the same command boundary."""
    payload = request.json if request is not None else None
    payload = payload if isinstance(payload, dict) else {}
    if command_service is None:
        return _command_response({
            'status': 'rejected',
            'reason': 'unavailable',
        })
    return _command_response(command_service.submit(
        'set_mode', 'web', payload.get('mode')))


@app.route('/api/led/status')
async def api_led_status(request):
    """Fast controller snapshot; no sensor or GPIO operation."""
    snapshot = command_service.snapshot() if command_service else {
        'available': False,
        'mode': 'unknown',
        'alert_active': False,
    }
    return Response(json.dumps(snapshot), headers={
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store'})


@app.route('/api/led/commands/<int:command_id>')
async def api_led_command_result(request, command_id):
    receipt = command_service.result(command_id) if command_service else None
    return Response(
        json.dumps(receipt or {
            'status': 'unknown',
            'reason': 'expired_or_unknown'
        }),
        status_code=200 if receipt else 404,
        headers={'Content-Type': 'application/json; charset=utf-8'})


@app.route('/api/publish', methods=['POST'])
async def api_publish(request):
    """
    API 端點：請求發布溫濕度數據到 MQTT。
    202 只代表請求已受理；實際結果由 /api/publish/status 查詢。
    """
    print("[Web] POST /api/publish")

    try:
        if mqtt_manager is None or publish_event is None:
            payload = {'status': 'unavailable', 'error': 'mqtt_not_initialized'}
            status_code = 503
        else:
            payload = mqtt_manager.request_publish(publish_event)
            status_code = 202 if payload['status'] == 'accepted' else 503

        return Response(
            json.dumps(payload),
            status_code=status_code,
            headers={'Content-Type': 'application/json; charset=utf-8'})
    except Exception as e:
        print(f"[Web] 發布異常: {e}")
        payload = {'status': 'failed', 'error': str(e)}
        return Response(
            json.dumps(payload),
            status_code=500,
            headers={'Content-Type': 'application/json; charset=utf-8'})


@app.route('/api/publish/status')
async def api_publish_status(request):
    """返回最近一次 MQTT 發佈請求的 accepted／published／failed 狀態。"""
    if mqtt_manager is None:
        payload = {'status': 'unavailable', 'error': 'mqtt_not_initialized'}
        status_code = 503
    else:
        payload = mqtt_manager.publish_status()
        status_code = 200
    return Response(
        json.dumps(payload),
        status_code=status_code,
        headers={
            'Content-Type': 'application/json; charset=utf-8',
            'Cache-Control': 'no-store'})


@app.route('/api/status')
async def api_status(request):
    """
    API 端點：返回系統狀態
    """
    print("[Web] GET /api/status")
    response_json = '{"status": "ok", "message": "System running"}'
    return Response(response_json, headers={'Content-Type': 'application/json; charset=utf-8'})


# ==================== Web Server 主協程 ====================

async def web_server_task():
    """
    Web Server 主任務
    監聽 80 端口，提供 HTTP 服務 (原生 Socket / uasyncio 版本)
    """
    print("\n" + "="*60)
    print("Socket Web Server 初始化")
    print("="*60 + "\n")
    
    # 先載入 HTML
    load_html()
    
    try:
        # 獲取 WiFi IP 地址
        wifi_ip = get_wifi_ip()
        
        if wifi_ip:
            print(f"[Web] WiFi IP 地址: {wifi_ip}")
            print(f"[Web] 訪問: http://{wifi_ip}")
            print(f"[Web] 或訪問: http://{wifi_ip}:80")
        else:
            print("[Web] ⚠️ 未能獲取 WiFi IP 地址")
            print("[Web] 訪問: http://ESP32_IP_ADDRESS")
        
        print("[Web] Socket Web 服務器啟動 (無 Microdot，超輕量)")
        print("[Web] 監聽端口: 80")
        print("[Web] 狀態: ✅ 運行中\n")
        
        # 啟動 Socket Web Server
        await app.start_server(host='0.0.0.0', port=80, debug=False)
    
    except Exception as e:
        print(f"[Web] ❌ Web Server 異常: {e}")
        import traceback
        traceback.print_exc()


async def sensor_monitor_task():
    """
    傳感器監控任務（可選）
    定期檢查傳感器狀態
    """
    try:
        while True:
            await uasyncio.sleep(10)
    except Exception as e:
        print(f"[Web] 傳感器監控異常: {e}")


# ==================== 主程序進入點 ====================

if __name__ == '__main__':
    print("[Web] web_server.py 已加載")
    print("[Web] 等待 main.py 調用...")
