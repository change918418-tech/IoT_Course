"""
communication/mqtt_client.py - MQTT 客戶端管理（修正版 v1.1.2）
基於 mqtt_as 庫
"""

import uasyncio
from mqtt_as import MQTTClient, config as mqtt_config


class MqttManager:
    """
    MQTT 客戶端管理器。

    mqtt_as 以同步方式呼叫 subs_cb(topic, msg, retained)，
    因此本類別負責把同步 callback 安全轉交給應用層。
    """

    CONNECT_CONFIRM_TIMEOUT_SEC = 5

    def __init__(self, ssid, password, broker='broker.emqx.io'):
        """
        初始化 MQTT 管理器

        參數:
            ssid: WiFi SSID
            password: WiFi 密碼
            broker: MQTT Broker 地址
        """
        self.ssid = ssid
        self.password = password
        self.broker = broker

        # MQTT 配置
        mqtt_config['ssid'] = ssid
        mqtt_config['wifi_pw'] = password
        mqtt_config['server'] = broker
        mqtt_config['subs_cb'] = self.on_message
        mqtt_config['connect_coro'] = self.on_connected

        self._connected = False
        self._connected_event = uasyncio.Event()
        self._message_callback = None
        self._last_publish_error = None
        self._publish_sequence = 0
        self._publish_state = {
            'status': 'idle',
            'request_id': None,
            'error': None,
        }

        self.client = MQTTClient(mqtt_config)

        print("[MQTT] 客戶端已初始化")

    async def connect(self):
        """
        連線到 MQTT Broker。

        返回: True 代表已由 connect_coro 確認連線，False 代表失敗或未確認。
        """
        try:
            print(f"[MQTT] 嘗試連線到 {self.broker}...")
            await self.client.connect()

            if not await self.wait_connected(self.CONNECT_CONFIRM_TIMEOUT_SEC):
                print("[MQTT] 連線未取得確認")
                return False

            print(f"[MQTT] 已連線到 {self.broker}")
            return True
        except Exception as e:
            self._set_disconnected()
            print("[MQTT] 連線失敗: {}: {}".format(type(e).__name__, e))
            return False

    async def wait_connected(self, timeout_sec=30):
        """
        等待 MQTT 已連線。

        參數:
            timeout_sec: 超時時間（秒）

        返回: True 連線成功，False 超時或目前未連線。
        """
        if self.is_connected():
            return True

        try:
            await uasyncio.wait_for(
                self._connected_event.wait(), timeout_sec)
        except uasyncio.TimeoutError:
            print("[MQTT] 等待連線超時")
            return False

        return self.is_connected()

    async def publish(self, topic, message, qos=0):
        """
        發佈 MQTT 訊息。

        返回: True 代表 client.publish 完成，False 代表未連線或發佈失敗。
        """
        self._last_publish_error = None
        if not self.is_connected():
            self._last_publish_error = 'not_connected'
            print("[MQTT] 發佈跳過：尚未連線")
            return False

        try:
            if isinstance(topic, str):
                topic = topic.encode()
            if isinstance(message, str):
                message = message.encode()

            await self.client.publish(topic, message, qos=qos)
            print(f"[MQTT] 已發佈: {topic.decode() if isinstance(topic, bytes) else topic}")
            return True
        except Exception as e:
            self._last_publish_error = '{}: {}'.format(type(e).__name__, e)
            print(f"[MQTT] 發佈失敗: {self._last_publish_error}")
            return False

    async def subscribe(self, topic, qos=0, callback=None):
        """
        訂閱 MQTT 主題並保存應用層 callback。

        callback 必須接受 (topic, msg, retained) 三個參數；
        mqtt_as 的底層 callback 是同步呼叫。
        """
        if callback is not None and not callable(callback):
            print("[MQTT] 訂閱失敗：callback 不可呼叫")
            return False
        if callback is not None:
            self._message_callback = callback
        if not self.is_connected():
            print("[MQTT] 訂閱跳過：尚未連線")
            return False

        try:
            if isinstance(topic, str):
                topic = topic.encode()

            await self.client.subscribe(topic, qos=qos)
            print(f"[MQTT] 已訂閱: {topic.decode() if isinstance(topic, bytes) else topic}")
            return True
        except Exception as e:
            print("[MQTT] 訂閱失敗: {}: {}".format(type(e).__name__, e))
            return False

    def request_publish(self, publish_event):
        """
        登記一次溫濕度發佈請求。

        Event 仍保留目前的合併語意；request_id 追蹤最近一次受理的請求。
        """
        if not self.is_connected():
            self._publish_state = {
                'status': 'unavailable',
                'request_id': None,
                'error': 'not_connected',
            }
            return dict(self._publish_state)

        self._publish_sequence += 1
        self._publish_state = {
            'status': 'accepted',
            'request_id': self._publish_sequence,
            'error': None,
        }
        publish_event.set()
        return dict(self._publish_state)

    def publish_status(self):
        """返回最近一次 MQTT 發佈請求的 RAM 快照。"""
        return dict(self._publish_state)

    def mark_publish_started(self):
        if self._publish_state['status'] == 'accepted':
            self._publish_state['status'] = 'publishing'

    def mark_publish_finished(self, success):
        if success:
            self._publish_state['status'] = 'published'
            self._publish_state['error'] = None
        else:
            self._publish_state['status'] = 'failed'
            self._publish_state['error'] = (
                self._last_publish_error or 'publish_failed')

    async def disconnect(self):
        """斷線連接。"""
        try:
            await self.client.disconnect()
        except Exception as e:
            print(f"[MQTT] 斷線失敗: {e}")
        finally:
            self._set_disconnected()
            print("[MQTT] 已斷線")

    async def on_connected(self, client):
        """mqtt_as 連線成功 callback；可在初次連線及重連時執行。"""
        self._connected = True
        self._connected_event.set()
        print("[MQTT] 已連線成功")

    def on_message(self, topic, msg, retained):
        """
        mqtt_as 的同步收訊 callback。

        不在此處直接操作硬體；只記錄訊息並轉交已註冊的應用 callback。
        """
        msg_str = msg.decode() if isinstance(msg, bytes) else msg
        topic_str = topic.decode() if isinstance(topic, bytes) else topic
        print(f"[MQTT] 收到訊息: {topic_str} = {msg_str}")

        callback = self._message_callback
        if callback is None:
            return

        try:
            result = callback(topic, msg, retained)
            if result is not None and hasattr(result, '__await__'):
                uasyncio.create_task(result)
        except Exception as e:
            print("[MQTT] 收訊 callback 失敗: {}: {}".format(
                type(e).__name__, e))

    def is_connected(self):
        """
        檢查連線狀態。

        若底層 client 提供 isconnected()，同步確認其實際狀態；
        這避免只依賴過期的 Python 布林旗標。
        """
        if not self._connected:
            return False

        checker = getattr(self.client, 'isconnected', None)
        if callable(checker):
            try:
                if not checker():
                    self._set_disconnected()
                    return False
            except Exception:
                self._set_disconnected()
                return False
        return True

    def _set_disconnected(self):
        self._connected = False
        self._connected_event.clear()
