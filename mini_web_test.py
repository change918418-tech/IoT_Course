"""
mini_web_test.py - ESP32 原生 Socket Web Server 極簡獨立測試腳本
用途：在 Thonny 中直接執行此檔案，用來排查 Web Server 是否能正常連線與顯示頁面。
"""

import gc
import socket
import network
import time

try:
    import uasyncio
except ImportError:
    import asyncio as uasyncio

try:
    import config
except ImportError:
    config = None


def connect_wifi_simple():
    """使用 config.py 中的 WiFi 設定連線，若已連線則直接返回 IP。"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan.ifconfig()[0]

    if not config or not hasattr(config, 'WIFI_PROFILES'):
        print("[WiFi] ⚠️ 找不到 config.WIFI_PROFILES，請確認 config.py 存在")
        return None

    print("[WiFi] 正在連接 WiFi...")
    for ssid, pwd in config.WIFI_PROFILES.items():
        print(f"[WiFi] 嘗試連接 SSID: {ssid}...")
        wlan.connect(ssid, pwd)
        for _ in range(20):
            if wlan.isconnected():
                ip = wlan.ifconfig()[0]
                print(f"[WiFi] ✅ 連線成功！IP 位址: {ip}")
                return ip
            time.sleep(0.5)
        print(f"[WiFi] 連接 {ssid} 超時，嘗試下一個...")

    print("[WiFi] ❌ 所有 WiFi 連線嘗試失敗")
    return None


async def handle_client(reader, writer):
    """處理單一 HTTP 連線。"""
    try:
        line = await reader.readline()
        if not line:
            return
        parts = line.decode('utf-8').strip().split()
        method = parts[0].upper() if len(parts) > 0 else 'GET'
        path = parts[1] if len(parts) > 1 else '/'
        print(f"\n[Test-Server] 🌐 收到請求: {method} {path}")

        # 讀取並丟棄所有 HTTP 標頭
        while True:
            hline = await reader.readline()
            if not hline or hline in (b'\r\n', b'\n'):
                break

        gc.collect()
        free_ram = gc.mem_free()

        # 生成測試網頁 HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ESP32 Socket 測試成功</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; text-align: center; padding: 40px 15px; margin: 0; }}
        .card {{ background: white; border-radius: 12px; max-width: 480px; margin: 0 auto; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
        h1 {{ color: #2ecc71; margin-top: 0; }}
        .stat {{ background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 12px; margin: 15px 0; font-size: 16px; color: #333; }}
        .btn {{ display: inline-block; background: #3498db; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 15px; }}
        .btn:hover {{ background: #2980b9; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>✅ Socket Web Server 正常運行！</h1>
        <p>恭喜！ESP32 原生 Socket 伺服器已成功接收請求並回傳此網頁。</p>
        <div class="stat">
            <strong>目前可用 RAM (Heap)：</strong> {free_ram:,} 位元組
        </div>
        <div class="stat">
            <strong>請求路徑：</strong> {path}
        </div>
        <p style="color: #666; font-size: 14px;">此測試證明：ESP32 的網路連線、Port 80 監聽與 HTTP 回傳皆完全暢通！</p>
    </div>
</body>
</html>"""

        body_bytes = html.encode('utf-8')
        headers = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: text/html; charset=utf-8\r\n",
            b"Connection: close\r\n",
            f"Content-Length: {len(body_bytes)}\r\n".encode('utf-8'),
            b"\r\n"
        ]

        # 寫入狀態與標頭
        writer.write(b"".join(headers))
        if hasattr(writer, 'drain'):
            await writer.drain()

        # 分塊寫入 HTML (每 1024 位元組)
        chunk_size = 1024
        for i in range(0, len(body_bytes), chunk_size):
            writer.write(body_bytes[i:i + chunk_size])
            if hasattr(writer, 'drain'):
                await writer.drain()

        print(f"[Test-Server] ✅ 成功發送測試網頁 ({len(body_bytes)} 位元組)")
    except Exception as e:
        print(f"[Test-Server] ❌ 處理請求時出錯: {e}")
    finally:
        try:
            writer.close()
            if hasattr(writer, 'wait_closed'):
                await writer.wait_closed()
        except Exception:
            pass


async def main():
    print("\n" + "="*50)
    print("ESP32 Socket Web Server 極簡測試工具")
    print("="*50 + "\n")

    ip = connect_wifi_simple()
    if not ip:
        print("[Error] 無法連接 WiFi，終止測試。")
        return

    print("\n" + "-"*50)
    print(f"請在手機或電腦瀏覽器開啟網址：")
    print(f"👉 http://{ip}/")
    print("-"*50 + "\n")

    # 啟動 Socket 伺服器
    server = await uasyncio.start_server(handle_client, '0.0.0.0', 80)
    print("[Test-Server] 伺服器已在 Port 80 監聽中，等待瀏覽器連線...\n")

    if hasattr(server, 'wait_closed'):
        await server.wait_closed()
    else:
        while True:
            await uasyncio.sleep(3600)


if __name__ == '__main__':
    try:
        uasyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Test-Server] 測試已停止")
