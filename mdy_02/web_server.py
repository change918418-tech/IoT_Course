"""
web_server.py - Microdot Web Server for IoT System v1.2
包含：
  - 輕量級Web框架（Microdot）
  - REST API 端點
  - 前端 HTML UI（從 index.html 導入）
  - WiFi IP 地址檢測和顯示
  - ✅ 光照 ADC 數據支持
"""

from microdot import Microdot, Response
import network
import uasyncio
try:
    import ujson as json
except ImportError:
    import json
from hardware.rfid import new_rfid_state
from hardware.motion import new_motion_state
import config

# ==================== 全局變數 ====================

app = Microdot()

# 由 main.py 設置的全局變數
mqtt_manager = None
publish_event = None
dht_sensor = None
led_service = None
light_sensor = None  # ✅ 新增光照傳感器
rfid_state = new_rfid_state()  # main 注入同一份 RAM 狀態；API 不操作 SPI
motion_state = new_motion_state()

# HTML 頁面（從 index.html 導入）
HTML_PAGE = None

def load_html():
    """載入 HTML 頁面"""
    global HTML_PAGE
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            HTML_PAGE = f.read()
        print("[Web] ✅ index.html 已載入")
    except Exception as e:
        print(f"[Web] ❌ 載入 index.html 失敗: {e}")
        HTML_PAGE = '<html><head><meta charset="utf-8"><title>IoT Web Server</title></head><body><h1>IoT Web Server</h1><p>❌ index.html 文件未找到</p><p>錯誤詳情: {}</p></body></html>'.format(str(e))


# ==================== 工具函數 ====================

def get_wifi_ip():
    """
    獲取 ESP32 WiFi IP 地址
    返回: IP 地址字符串 或 None
    """
    try:
        wlan = network.WLAN(network.STA_IF)
        
        if wlan.isconnected():
            config = wlan.ifconfig()
            ip = config[0]
            return ip
        else:
            return None
    except:
        return None


def get_current_temperature():
    """獲取當前溫度"""
    try:
        if dht_sensor:
            return dht_sensor.temperature
    except:
        pass
    return None


def get_current_humidity():
    """獲取當前濕度"""
    try:
        if dht_sensor:
            return dht_sensor.humidity
    except:
        pass
    return None


def get_current_light():
    """
    獲取當前光照值 (ADC 值)
    ✅ 修復：直接從 light_sensor 對象讀取
    """
    try:
        if light_sensor:
            # 如果 light_sensor 有 read() 方法，則調用它
            if hasattr(light_sensor, 'read'):
                return light_sensor.read()
            # 如果 light_sensor 本身就是 ADC 對象，直接讀取值
            elif hasattr(light_sensor, 'value'):
                return light_sensor.value
            else:
                return light_sensor.read()
    except Exception as e:
        print(f"[Web] ⚠️ 讀取光照值異常: {e}")
    return 0


# ==================== Web 路由 ====================

@app.route('/')
async def index(request):
    """
    主頁面：返回 HTML UI
    """
    print("[Web] GET / (主頁)")
    
    if HTML_PAGE is None:
        load_html()
    
    # 正確的方式：設置 Content-Type 為 text/html
    return Response(HTML_PAGE, headers={'Content-Type': 'text/html; charset=utf-8'})


@app.route('/index.html')
async def index_html(request):
    """
    /index.html 路由（備用）
    """
    print("[Web] GET /index.html")
    
    if HTML_PAGE is None:
        load_html()
    
    return Response(HTML_PAGE, headers={'Content-Type': 'text/html; charset=utf-8'})


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
    """
    API 端點：返回傳感器數據（JSON 格式）
    ✅ 修復：添加光照值返回
    返回：{ temp, humidity, light, light_thresholds, status, rfid: 最後讀取狀態快照 }
    """
    #print("[Web] GET /api/data")
    
    temp = get_current_temperature()
    humidity = get_current_humidity()
    light = get_current_light()  # ✅ 獲取光照值
    
    # 格式化溫度和濕度到一位小數
    if temp is not None:
        temp = round(temp, 1)
    if humidity is not None:
        humidity = round(humidity, 1)
    
    # 序列化保證 None -> null，錯誤訊息中的引號也會正確跳脫。
    response_json = json.dumps({
        'temp': temp, 'humidity': humidity, 'light': light,
        'light_thresholds': {
            'trigger': config.LIGHT_ALERT_TRIGGER_ADC,
            'reset': config.LIGHT_ALERT_RESET_ADC
        },
        'status': 'ok', 'rfid': dict(rfid_state), 'motion': dict(motion_state),
        'led': led_service.snapshot() if led_service else
               {'available': False, 'alert_active': False,
                'alert_flash_count': 0,
                'alert_flash_total': getattr(config, 'LIGHT_ALERT_BLINK_COUNT', 5),
                'alert_flash_log': []}
    })
    
    #print(f"[Web] API 返回: 溫度={temp}, 濕度={humidity}, 光照={light}")
    
    return Response(response_json, headers={'Content-Type': 'application/json; charset=utf-8'})

@app.route('/api/motion/status')
async def api_motion_status(request):
    """快速回傳PIR／喇叭RAM快照，不讀取DHT、ADC或SPI。"""
    return Response(json.dumps(dict(motion_state)), headers={
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store'})


@app.route('/api/led/toggle', methods=['POST'])
async def api_led_toggle(request):
    """
    API 端點：切換 LED 顏色
    返回：{ status: 'ok' }
    """
    print("[Web] POST /api/led/toggle")
    
    if led_service is None:
        return Response(json.dumps({'status': 'rejected', 'reason': 'unavailable'}),
                        status_code=503, headers={'Content-Type': 'application/json; charset=utf-8'})
    receipt = led_service.submit('cycle', 'web')
    status = 202 if receipt['status'] == 'accepted' else {
        'busy': 409, 'queue_full': 429, 'stopped': 503
    }.get(receipt['reason'], 400)
    return Response(json.dumps(receipt), status_code=status,
                    headers={'Content-Type': 'application/json; charset=utf-8'})


@app.route('/api/led/status')
async def api_led_status(request):
    """Fast snapshot only: no ADC, DHT, SPI or GPIO operation."""
    snapshot = led_service.snapshot() if led_service else {
        'available': False, 'alert_active': False,
        'alert_flash_count': 0,
        'alert_flash_total': getattr(config, 'LIGHT_ALERT_BLINK_COUNT', 5),
        'alert_flash_log': []
    }
    return Response(json.dumps(snapshot), headers={
        'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'})


@app.route('/api/led/commands/<int:command_id>')
async def api_led_command_result(request, command_id):
    receipt = led_service.result(command_id) if led_service else None
    return Response(json.dumps(receipt or {'status': 'unknown', 'reason': 'expired_or_unknown'}),
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
    返回：{ status: 'ok', uptime: 運行時間 }
    """
    print("[Web] GET /api/status")
    
    response_json = '{"status": "ok", "message": "System running"}'
    return Response(response_json, headers={'Content-Type': 'application/json; charset=utf-8'})


# ==================== Web Server 主協程 ====================

async def web_server_task():
    """
    Web Server 主任務
    監聽 80 端口，提供 HTTP 服務
    """
    print("\n" + "="*60)
    print("Web Server 初始化")
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
        
        print("[Web] Microdot Web 服務器啟動")
        print("[Web] 監聽端口: 80")
        print("[Web] 狀態: ✅ 運行中\n")
        
        # 啟動 Web Server（阻塞）
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
            
            # 可在此添加定期檢查邏輯
            # print("[Web] 傳感器監控中...")
    
    except Exception as e:
        print(f"[Web] 傳感器監控異常: {e}")


# ==================== 主程序進入點 ====================

if __name__ == '__main__':
    print("[Web] web_server.py 已加載")
    print("[Web] 等待 main.py 調用...")
