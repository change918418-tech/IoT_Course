"""
tasks.py - 非同步任務協程（修正版 v1.1.3）
已整合 aiot_tools 和 ns_tools 的時間函數
修正：OLED 顯示搬到 hardware.display，並修正 NoneType 錯誤
"""

import uasyncio
import time
import config
from hardware.button import Button
from hardware.sensors import Dht11Sensor, LightSensor
from hardware.display import OledDisplay
from communication.wifi import get_current_time


# ==================== 任務：按鈕監聽 ====================

async def button1_task(button1, led_service, publish_event):
    """
    按鈕 1 監聽任務
    功能：按下按鈕1時，循環切換 LED 顏色
    """
    button_id = 1
    print(f"[Task] 按鈕 {button_id} 監聽已啟動")

    while True:
        try:
            await button1.wait_press(reject_if=lambda: led_service.busy)
            print(f"[Button] 按鈕 {button_id} 被按下")

            if button1.press_rejected:
                print('[Button] 警示期間按下，不執行；請放開後重新按下')
            else:
                receipt = led_service.submit('cycle', 'button1')
                print('[Button] LED 命令:', receipt)

            await button1.wait_release()
            print(f"[Button] 按鈕 {button_id} 被釋放")

            await uasyncio.sleep_ms(100)
        except Exception as e:
            print(f"[Error] 按鈕 {button_id} 任務異常: {e}")
            await uasyncio.sleep(1)


async def button2_task(button2, dht_sensor, mqtt_manager, publish_event):
    """
    按鈕 2 監聽任務
    功能：按下按鈕2時，讀取溫濕度並透過 MQTT 發佈
    """
    button_id = 2
    print(f"[Task] 按鈕 {button_id} 監聽已啟動")

    while True:
        try:
            await button2.wait_press()
            print(f"[Button] 按鈕 {button_id} 被按下")

            publish_event.set()
            print("[Task] 觸發溫濕度發佈事件")

            await button2.wait_release()
            print(f"[Button] 按鈕 {button_id} 被釋放")

            await uasyncio.sleep_ms(100)
        except Exception as e:
            print(f"[Error] 按鈕 {button_id} 任務異常: {e}")
            await uasyncio.sleep(1)


# ==================== 任務：感測器讀取 ====================

async def pir_monitor_task(pir_sensor, motion_event, motion_state=None):
    """非同步穩定邊緣防抖：穩定高電位觸發一次，穩定低電位後重新武裝。"""
    if pir_sensor is None:
        print('[Task] PIR 未初始化，跳過偵測任務')
        return
    interval = getattr(config, 'PIR_POLL_INTERVAL_MS', 100)
    high_debounce_ms = getattr(config, 'PIR_HIGH_DEBOUNCE_MS', 200)
    low_rearm_ms = getattr(config, 'PIR_LOW_REARM_MS', 1500)
    detected_hold_ms = getattr(config, 'MOTION_DETECTED_HOLD_MS', 5000)
    print(f'[Task] PIR 偵測已啟動，輪詢={interval} ms')
    armed = True
    high_since = None
    low_since = None
    last_detection_ms = None
    while True:
        try:
            current = pir_sensor.is_motion()
            now_ms = time.ticks_ms()
            if current:
                low_since = None
                if armed:
                    if high_since is None:
                        high_since = now_ms
                    elif time.ticks_diff(now_ms, high_since) >= high_debounce_ms:
                        armed = False
                        high_since = None
                        last_detection_ms = now_ms
                        motion_event.set()
                        date_str, _, time_str = get_current_time()
                        detected_at = '{} {}'.format(date_str, time_str)
                        if motion_state is not None:
                            motion_state['last_detected_at'] = detected_at
                            motion_state['recent_detections'].append(detected_at)
                            if len(motion_state['recent_detections']) > 5:
                                motion_state['recent_detections'].pop(0)
                            motion_state['count'] += 1
                        print('[PIR] 偵測到移動，時間：{}，觸發音樂'.format(detected_at))
            else:
                high_since = None
                if not armed:
                    if low_since is None:
                        low_since = now_ms
                    elif time.ticks_diff(now_ms, low_since) >= low_rearm_ms:
                        armed = True
                        low_since = None
                else:
                    low_since = None
            if motion_state is not None:
                motion_state['sensor_status'] = 'ready'
                motion_state['sensor_error'] = None
                motion_state['pir_high'] = current
                motion_state['detected'] = current or (
                    last_detection_ms is not None and
                    time.ticks_diff(now_ms, last_detection_ms) < detected_hold_ms)
                if not motion_state['detected']:
                    last_detection_ms = None
        except Exception as e:
            high_since = None
            low_since = None
            if motion_state is not None:
                motion_state['sensor_status'] = 'error'
                motion_state['sensor_error'] = str(e)
                motion_state['detected'] = False
                motion_state['pir_high'] = False
            print(f'[Error] PIR 讀取異常: {e}')
        await uasyncio.sleep_ms(interval)


async def music_on_motion_task(speaker, motion_event, motion_state=None):
    """唯一喇叭使用者；播放中的事件合併為最多一次待播。"""
    if speaker is None:
        print('[Task] 喇叭未初始化，跳過播放任務')
        return
    melody = getattr(config, 'MOTION_MELODY',
                     (('C4', 0.3), ('E4', 0.3), ('D4', 0.3), ('G3', 0.3), ('REST', 0.2)))
    print('[Task] 音樂任務已啟動，等待移動事件')
    try:
        while True:
            await motion_event.wait()
            motion_event.clear()
            try:
                if motion_state is not None:
                    motion_state['music_status'] = 'playing'
                    motion_state['music_error'] = None
                print('[Speaker] 播放移動提示音樂')
                await speaker.play_song(melody)
                print('[Speaker] 播放完成，已靜音')
                if motion_state is not None:
                    motion_state['music_status'] = 'completed'
            except Exception as e:
                if motion_state is not None:
                    motion_state['music_status'] = 'error'
                    motion_state['music_error'] = str(e)
                print(f'[Error] 音樂播放異常: {e}')
                await uasyncio.sleep(1)
    finally:
        speaker.silence()
        if motion_state is not None:
            motion_state['music_status'] = 'stopped'


async def dht11_read_task(dht_sensor):
    """
    DHT11 溫濕度讀取任務
    定期讀取溫濕度，並儲存最新資料供其他任務使用
    """
    print("[Task] DHT11 讀取任務已啟動")

    while True:
        try:
            result = dht_sensor.measure()
            if result:
                temp, humi = result
                #print(f"[DHT11] 溫度: {temp}℃, 濕度: {humi}%")
            else:
                print("[DHT11] 量測失敗，使用上次資料")

            await uasyncio.sleep(config.DHT11_POLL_INTERVAL_SEC)
        except Exception as e:
            print(f"[Error] DHT11 任務異常: {e}")
            await uasyncio.sleep(config.DHT11_POLL_INTERVAL_SEC)


async def light_sensor_task(light_sensor, led_service):
    """Hysteresis producer; no GPIO and no effect sequencing."""
    print('[Task] 光照命令生產者已啟動')
    armed = True
    while True:
        try:
            brightness = light_sensor.read()
            if getattr(config, 'LIGHT_ALERT_ENABLED', True) and not led_service.busy:
                if brightness >= getattr(config, 'LIGHT_ALERT_RESET_ADC', 1100):
                    armed = True
                elif armed and brightness < getattr(config, 'LIGHT_ALERT_TRIGGER_ADC', 1000):
                    receipt = led_service.submit('low_light_alert', 'light')
                    if receipt['status'] == 'accepted':
                        armed = False
                    print('[Light] LED 命令:', receipt)
        except Exception as e:
            print('[Error] 光照取樣異常:', e)
        await uasyncio.sleep_ms(config.LIGHT_POLL_INTERVAL_MS)


# ==================== 任務：顯示更新 ====================

async def rfid_read_task(rfid_reader, rfid_state):
    """唯一讀卡者：500 ms 輪詢，將最後成功結果提供給 Web API。"""
    if rfid_reader is None:
        print("[Task] RFID 未初始化，跳過讀卡任務")
        return
    print("[Task] RFID 讀卡任務已啟動")
    while True:
        try:
            uid = await rfid_reader.read_uid()
            if uid is not None:
                date_str, weekday_str, time_str = get_current_time()
                read_at = '{} {}'.format(date_str, time_str)
                # 更新期間沒有 await；協作式排程下 API 不會讀到半份紀錄。
                rfid_state['last_uid'] = uid
                rfid_state['last_read_at'] = read_at
                rfid_state['recent_reads'].append({'uid': uid, 'read_at': read_at})
                if len(rfid_state['recent_reads']) > 5:
                    rfid_state['recent_reads'].pop(0)
                rfid_state['status'] = 'ready'
                rfid_state['error'] = None
                print('RFID：', uid)
            # 無卡不清除最後紀錄；錯誤只在下一次成功讀卡後解除。
        except Exception as e:
            rfid_state['status'] = 'read_error'
            rfid_state['error'] = str(e)
            print(f"[Error] RFID 讀卡異常: {e}")
        await uasyncio.sleep_ms(config.RFID_POLL_INTERVAL_MS)


async def oled_display_task(dht_sensor):
    """
    OLED 顯示更新任務（修正版）
    每秒更新 OLED 螢幕，顯示時間、溫濕度等資訊

    功能：
    • 第一行：日期、星期、時間
    • 第二行：溫度、濕度
    使用 hardware.display.OledDisplay 負責硬體初始化
    """
    print("[Task] OLED 顯示任務已啟動")

    oled = None
    try:
        oled = OledDisplay()
        print("[OLED] 初始化成功（由 hardware.display 管理）")
    except Exception as e:
        print(f"[OLED] 初始化失敗: {e}")
        print("[OLED] 使用簡化模式（只輸出日誌）")
        oled = None

    while True:
        try:
            # 取得時間與溫溼度
            date_str, weekday_str, time_str = get_current_time()
            temp, humi = dht_sensor.get_data()

            # 防呆：避免 NoneType 傳到字型庫
            date_str = "" if date_str is None else str(date_str)
            weekday_str = "" if weekday_str is None else str(weekday_str)
            time_str = "" if time_str is None else str(time_str)

            temp = 0 if temp is None else temp
            humi = 0 if humi is None else humi

            line1 = f"{date_str} 週{weekday_str} {time_str[:5]}"
            line2 = f"溫度：{temp}℃ 濕度：{humi}%"

            if oled is not None:
                try:
                    oled.show_two_lines(line1, line2)
                except Exception as e:
                    print(f"[OLED] 顯示更新異常: {e}")

            #print(f"[Display] {line1} | 溫: {temp}℃ 濕: {humi}%")

            await uasyncio.sleep(1)
        except Exception as e:
            print(f"[Error] OLED 顯示任務異常: {e}")
            await uasyncio.sleep(1)


# ==================== 任務：MQTT 發佈 ====================

async def mqtt_publish_task(dht_sensor, mqtt_manager, publish_event):
    """
    MQTT 發佈任務
    監聽 publish_event，在事件觸發時發佈溫濕度訊息
    """
    print("[Task] MQTT 發佈任務已啟動")

    await mqtt_manager.wait_connected()
    print("[MQTT Pub] 已連線，開始監聽發佈事件")

    while True:
        try:
            await publish_event.wait()

            temp, humi = dht_sensor.get_data()
            temp = 0 if temp is None else temp
            humi = 0 if humi is None else humi

            message = f'{config.DEVICE_NAME}：溫度：{temp}℃, 濕度：{humi}%'

            success = await mqtt_manager.publish(
                config.MQTT_TOPICS['temp_humi'],
                message,
                qos=0
            )

            if success:
                print(f"[MQTT Pub] 溫濕度已發佈: {message}")
            else:
                print("[MQTT Pub] 發佈失敗")

            publish_event.clear()
            await uasyncio.sleep_ms(100)
        except Exception as e:
            print(f"[Error] MQTT 發佈任務異常: {e}")
            await uasyncio.sleep(1)


# ==================== 任務：MQTT 訂閱與指令處理 ====================

async def mqtt_subscribe_task(mqtt_manager, led_service):
    """
    MQTT 訂閱與指令處理任務
    監聽 MQTT 訂閱的訊息，並根據指令控制裝置
    """
    print("[Task] MQTT 訂閱任務已啟動")

    await mqtt_manager.wait_connected()
    print("[MQTT Sub] 已連線，開始監聽指令")

    async def handle_cmd(msg):
        try:
            msg_str = msg.decode() if isinstance(msg, bytes) else msg
            print(f"[MQTT Sub] 收到指令: {msg_str}")

            if 'led' in msg_str.lower():
                try:
                    led_value = int(msg_str.split(':')[-1].split('=')[-1].strip())
                    receipt = led_service.submit('set_color', 'mqtt', led_value)
                    print('[MQTT Sub] LED 命令:', receipt)
                except ValueError:
                    print("[MQTT Sub] 指令解析失敗（無效索引）")
                except Exception as e:
                    print(f"[MQTT Sub] 指令解析異常: {e}")
        except Exception as e:
            print(f"[Error] 指令處理異常: {e}")

    await mqtt_manager.subscribe(
        config.MQTT_TOPICS['cmd'],
        qos=0,
        callback=handle_cmd
    )

    while True:
        await uasyncio.sleep(10)
