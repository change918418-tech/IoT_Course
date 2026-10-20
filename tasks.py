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

async def button1_task(button1, command_service, publish_event):
    """
    按鈕 1 監聽任務。

    按鈕只產生命令，不在 adapter 內判斷 LED busy 或操作硬體。
    """
    button_id = 1
    print(f"[Task] 按鈕 {button_id} 監聽已啟動")

    while True:
        try:
            await button1.wait_press()
            print(f"[Button] 按鈕 {button_id} 被按下")
            receipt = command_service.submit('cycle', 'button1')
            print('[Button] LED 命令:', receipt)
            await button1.wait_release()
            print(f"[Button] 按鈕 {button_id} 被釋放")
            await uasyncio.sleep_ms(100)
        except Exception as e:
            print(f"[Error] 按鈕 {button_id} 任務異常: {e}")
            await uasyncio.sleep(1)



async def button2_task(button2, mqtt_manager, publish_event):
    """
    按鈕 2 監聽任務。

    只向 MQTT 發佈 adapter 提交請求，不讀取或改寫感測資料。
    """
    button_id = 2
    print(f"[Task] 按鈕 {button_id} 監聽已啟動")

    while True:
        try:
            await button2.wait_press()
            print(f"[Button] 按鈕 {button_id} 被按下")
            receipt = mqtt_manager.request_publish(publish_event)
            print("[Task] MQTT 溫濕度發佈請求:", receipt)
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


async def dht11_read_task(dht_sensor, sensor_snapshot=None):
    """
    DHT11 量測 producer；成功值與品質交給 SensorSnapshot。
    """
    print("[Task] DHT11 讀取任務已啟動")

    while True:
        try:
            result = dht_sensor.measure()
            if sensor_snapshot is not None:
                sensor_snapshot.update_dht(
                    result, getattr(dht_sensor, 'last_error', None))
            if result is None:
                print("[DHT11] 量測失敗，保留上次有效資料")
            await uasyncio.sleep(config.DHT11_POLL_INTERVAL_SEC)
        except Exception as e:
            if sensor_snapshot is not None:
                sensor_snapshot.update_dht(None, str(e))
            print(f"[Error] DHT11 任務異常: {e}")
            await uasyncio.sleep(config.DHT11_POLL_INTERVAL_SEC)


async def light_sensor_task(light_sensor, command_service, sensor_snapshot=None):
    """Light producer; samples and submits, but never applies LED effects."""
    print('[Task] 光照命令生產者已啟動')
    armed = True
    while True:
        try:
            brightness = light_sensor.read()
            sample_error = getattr(light_sensor, 'last_error', None)
            if sensor_snapshot is not None:
                sensor_snapshot.update_light(brightness, sample_error)
            if sample_error is not None or brightness is None:
                await uasyncio.sleep_ms(config.LIGHT_POLL_INTERVAL_MS)
                continue
            if getattr(config, 'LIGHT_ALERT_ENABLED', True):
                trigger = getattr(config, 'LIGHT_ALERT_TRIGGER_ADC', 1000)
                reset = getattr(config, 'LIGHT_ALERT_RESET_ADC', 1100)
                dark_when_high = getattr(config, 'LIGHT_DARK_WHEN_HIGH', False)
                is_reset = brightness <= reset if dark_when_high else brightness >= reset
                is_dark = brightness > trigger if dark_when_high else brightness < trigger
                if is_reset:
                    armed = True
                elif armed and is_dark:
                    receipt = command_service.submit('low_light_alert', 'light')
                    if receipt['status'] == 'accepted':
                        armed = False
                    print('[Light] LED 命令:', receipt)
        except Exception as e:
            if sensor_snapshot is not None:
                sensor_snapshot.update_light(None, str(e))
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


async def oled_display_task(sensor_snapshot):
    """
    OLED 顯示更新任務；只讀 SensorSnapshot，不直接量測 DHT。
    """
    print("[Task] OLED 顯示任務已啟動")

    oled = None
    try:
        oled = OledDisplay()
        print("[OLED] 初始化成功（由 hardware.display 管理）")
    except Exception as e:
        print(f"[OLED] 初始化失敗: {e}")
        print("[OLED] 使用簡化模式（只輸出日誌）")

    while True:
        try:
            date_str, weekday_str, time_str = get_current_time()
            snapshot = sensor_snapshot.snapshot()
            temp = snapshot['temperature']['value']
            humi = snapshot['humidity']['value']
            date_str = "" if date_str is None else str(date_str)
            weekday_str = "" if weekday_str is None else str(weekday_str)
            time_str = "" if time_str is None else str(time_str)
            temp = "--" if temp is None else temp
            humi = "--" if humi is None else humi
            line1 = f"{date_str} 週{weekday_str} {time_str[:5]}"
            line2 = f"溫度：{temp}℃ 濕度：{humi}%"
            if oled is not None:
                try:
                    oled.show_two_lines(line1, line2)
                except Exception as e:
                    print(f"[OLED] 顯示更新異常: {e}")
            await uasyncio.sleep(1)
        except Exception as e:
            print(f"[Error] OLED 顯示任務異常: {e}")
            await uasyncio.sleep(1)

# ==================== 任務：MQTT 發佈 ====================

async def mqtt_publish_task(sensor_snapshot, mqtt_manager, publish_event):
    """
    MQTT 發佈任務；只讀 SensorSnapshot，不直接讀取感測器。
    """
    print("[Task] MQTT 發佈任務已啟動")

    if not await mqtt_manager.wait_connected():
        print("[MQTT Pub] 未確認連線，停止發佈任務")
        return
    print("[MQTT Pub] 已確認連線，開始監聽發佈事件")

    while True:
        try:
            await publish_event.wait()
            mqtt_manager.mark_publish_started()
            snapshot = sensor_snapshot.snapshot()
            temp = snapshot['temperature']['value']
            humi = snapshot['humidity']['value']
            temp = 0 if temp is None else temp
            humi = 0 if humi is None else humi
            message = f'{config.DEVICE_NAME}：溫度：{temp}℃, 濕度：{humi}%'
            success = await mqtt_manager.publish(
                config.MQTT_TOPICS['temp_humi'], message, qos=0)
            mqtt_manager.mark_publish_finished(success)
            if success:
                print(f"[MQTT Pub] 溫濕度已發佈: {message}")
            else:
                print("[MQTT Pub] 發佈失敗")
        except Exception as e:
            mqtt_manager.mark_publish_finished(False)
            print(f"[Error] MQTT 發佈任務異常: {e}")
        finally:
            publish_event.clear()
        await uasyncio.sleep_ms(100)


# ==================== 任務：MQTT 訂閱與指令處理 ====================

async def mqtt_subscribe_task(mqtt_manager, command_service):
    """
    MQTT callback 只解析指令並送入 CommandService。

    P1 先維持 P0 的 led:4／led=4 wire format，內部統一成命令契約。
    """
    print("[Task] MQTT 訂閱任務已啟動")

    if not await mqtt_manager.wait_connected():
        print("[MQTT Sub] 未確認連線，停止訂閱任務")
        return

    def handle_cmd(topic, msg, retained):
        try:
            msg_str = msg.decode() if isinstance(msg, bytes) else msg
            print(f"[MQTT Sub] 收到指令: {msg_str}")
            if 'led' not in msg_str.lower():
                print("[MQTT Sub] 忽略未知指令")
                return
            try:
                led_value = int(msg_str.split(':')[-1].split('=')[-1].strip())
            except (TypeError, ValueError):
                print("[MQTT Sub] 指令解析失敗（無效索引）")
                return
            receipt = command_service.submit('set_color', 'mqtt', led_value)
            print('[MQTT Sub] LED 命令:', receipt)
        except Exception as e:
            print(f"[Error] 指令處理異常: {e}")

    subscribed = await mqtt_manager.subscribe(
        config.MQTT_TOPICS['cmd'], qos=0, callback=handle_cmd)
    if not subscribed:
        print("[MQTT Sub] 指令主題訂閱失敗")
        return

    print("[MQTT Sub] 已確認訂閱，開始監聽指令")
    while True:
        await uasyncio.sleep(10)
