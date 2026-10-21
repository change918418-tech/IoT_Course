"""
main.py - 主程式進入點（修正版 v1.2 - 含 Socket Web Server）
已整合 aiot_tools.py、ns_tools.py、mqtt_as 和 輕量 Socket Web Server
"""

import uasyncio
import sys

# 導入配置與模組
import config
from hardware.led import RgbLed
from services.led_controller import LedController
from services.command_service import CommandService
from services.sensor_snapshot import SensorSnapshot
from hardware.button import Button
from hardware.sensors import Dht11Sensor, LightSensor, PirSensor
from hardware.speaker import Speaker
from hardware.motion import new_motion_state
from hardware.display import OledDisplay
from hardware.rfid import RfidReader, new_rfid_state
from communication.mqtt_client import MqttManager

# 導入修正後的 WiFi 模組
from communication.wifi import connect_wifi, sync_time, get_current_time

# 導入任務
import tasks

# 導入 Web Server
import web_server


# ==================== 系統初始化 ====================

async def initialize_system():
    """
    初始化系統的所有硬體與通訊模組
    返回: LED、按鈕、感測器、MQTT、RFID 狀態、PIR 與喇叭元組
    """
    print("\n" + "="*60)
    print("系統初始化")
    print("="*60 + "\n")
    
    # 1. 初始化硬體
    print("[Init] 初始化 RGB LED...")
    rgb_led = RgbLed()
    
    print("[Init] 初始化按鈕...")
    button1 = Button(config.BUTTON1_PIN)
    button2 = Button(config.BUTTON2_PIN)
    button3 = Button(config.BUTTON3_PIN)
    
    print("[Init] 初始化感測器...")
    dht_sensor = Dht11Sensor()
    light_sensor = LightSensor()
    
    # 初次測量
    dht_sensor.measure()

    print("[Init] 初始化 RFID...")
    rfid_state = new_rfid_state()
    rfid_reader = None
    try:
        rfid_reader = RfidReader()
        rfid_state['status'] = 'ready'
    except Exception as e:
        rfid_state['status'] = 'init_error'
        rfid_state['error'] = str(e)
        print(f"[RFID] 初始化失敗: {e}，其他功能繼續運行")
    
    print("[Init] 硬體初始化完成\n")
    
    # 2. WiFi 連線
    ssid, password = await connect_wifi()
    
    # 3. 時間同步
    await sync_time()
    
    # 4. 初始化 MQTT
    print("[Init] 初始化 MQTT 客戶端...")
    mqtt_manager = MqttManager(ssid, password, broker='broker.emqx.io')
    
    mqtt_connected = False
    for attempt in range(1, 4):
        print(f"[Init] MQTT 連線嘗試 {attempt}/3...")
        try:
            if await mqtt_manager.connect():
                mqtt_connected = True
                print("[Init] MQTT 連線成功")
                break
        except Exception as e:
            print(f"[Init] MQTT 連線異常: {e}")
        
        if attempt < 3:
            await uasyncio.sleep(2)
    
    if not mqtt_connected:
        print("[Init] ⚠️ MQTT 連線失敗，但繼續運行（其他功能仍可用）")
    
    # 通訊初始化後再建立 PWM，後續進入 main 的 finally 管理資源。
    pir_sensor = None
    speaker = None
    try:
        pir_sensor = PirSensor()
    except Exception as e:
        print(f'[Init] PIR 初始化失敗: {e}')
    try:
        speaker = Speaker()
    except Exception as e:
        print(f'[Init] 喇叭初始化失敗: {e}')

    print("[Init] 系統初始化完成\n")
    
    return (rgb_led, button1, button2, button3, dht_sensor, light_sensor,
            mqtt_manager, rfid_reader, rfid_state, pir_sensor, speaker)


# ==================== 主非同步函式 ====================

async def main():
    """
    主程式：初始化系統並啟動所有協程
    """
    # 初始化系統
    (rgb_led, button1, button2, button3, dht_sensor, light_sensor,
     mqtt_manager, rfid_reader, rfid_state, pir_sensor, speaker) = await initialize_system()
    
    # 建立任務間通訊事件與共享資料契約
    publish_event = uasyncio.Event()
    motion_event = uasyncio.Event()
    sensor_snapshot = SensorSnapshot()
    sensor_snapshot.update_dht(
        dht_sensor.get_data(),
        getattr(dht_sensor, 'last_error', None))
    led_controller = LedController(rgb_led)
    command_service = CommandService(led_controller)
    led_owner = uasyncio.create_task(led_controller.run())
    motion_state = new_motion_state()
    motion_state['sensor_status'] = 'ready' if pir_sensor is not None else 'unavailable'
    motion_state['music_status'] = 'idle' if speaker is not None else 'unavailable'

    # 初始化 Web Server 的全局變數
    web_server.mqtt_manager = mqtt_manager
    web_server.publish_event = publish_event
    web_server.sensor_snapshot = sensor_snapshot
    web_server.command_service = command_service
    web_server.led_controller = led_controller
    web_server.rfid_state = rfid_state
    web_server.motion_state = motion_state
    
    try:
        print("[Main] 啟動所有協程...\n")
        
        # 使用 asyncio.gather() 同時啟動所有任務
        await uasyncio.gather(
            # 按鈕監聽任務
            tasks.button1_task(button1, command_service, publish_event),
            tasks.button2_task(button2, mqtt_manager, publish_event),
            tasks.button3_task(button3, command_service),

            # 感測器讀取任務
            tasks.dht11_read_task(dht_sensor, sensor_snapshot),
            tasks.light_sensor_task(light_sensor, command_service, sensor_snapshot),
            led_owner,
            tasks.rfid_read_task(rfid_reader, rfid_state),
            tasks.pir_monitor_task(pir_sensor, motion_event, motion_state),
            tasks.music_on_motion_task(speaker, motion_event, motion_state),

            # 顯示與通訊任務
            tasks.oled_display_task(sensor_snapshot),
            tasks.mqtt_publish_task(sensor_snapshot, mqtt_manager, publish_event),
            tasks.mqtt_subscribe_task(mqtt_manager, command_service),

            # Web Server 任務
            web_server.web_server_task(),
            web_server.sensor_monitor_task(),
        )
    
    except KeyboardInterrupt:
        print("\n[Main] 程式被使用者中斷")
        led_controller.request_stop()

    except Exception as e:
        print(f"\n[Error] 主程式異常: {e}")
        print("[Error] 進行緊急清理...")
        led_controller.request_stop()
        try:
            await mqtt_manager.disconnect()
        except:
            pass
        raise
    finally:
        led_controller.request_stop()
        await led_controller.wait_stopped()
        if speaker is not None:
            speaker.deinit()


# ==================== 程式進入點 ====================

if __name__ == '__main__':
    print("\n")
    print("╔" + "═"*58 + "╗")
    print("║" + " "*12 + "IoT 教學專案 - ESP32 多感測器系統" + " "*12 + "║")
    print("║" + " "*15 + "含 Web Server (Socket)" + " "*21 + "║")
    print("╚" + "═"*58 + "╝")
    print("\n")
    
    try:
        # 執行主程式
        uasyncio.run(main())
    
    except Exception as e:
        print("\n[Fatal Error] 致命錯誤: {}: {}".format(type(e).__name__, e))
    
    finally:
        print("\n[Shutdown] 程式結束\n")
