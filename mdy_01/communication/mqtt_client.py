"""
communication/mqtt_client.py - MQTT 客戶端管理（修正版 v1.1.2）
基於 mqtt_as 庫
"""

import uasyncio
from mqtt_as import MQTTClient, config as mqtt_config


class MqttManager:
    """
    MQTT 客戶端管理器
    """
    
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
        mqtt_config['subs_cb'] = self.on_message       # 訂閱回調
        mqtt_config['connect_coro'] = self.on_connected  # 連線回調
        
        # 是否已連線
        self._connected = False
        self._connected_event = uasyncio.Event()
        
        # 初始化 MQTT 客戶端
        self.client = MQTTClient(mqtt_config)
        
        print("[MQTT] 客戶端已初始化")
    
    
    async def connect(self):
        """
        連線到 MQTT Broker
        
        返回: True 連線成功，False 連線失敗
        """
        try:
            print(f"[MQTT] 嘗試連線到 {self.broker}...")
            
            # 連線到 MQTT
            await self.client.connect()
            
            # 等待 connected_coro 完成
            await uasyncio.sleep(2)
            
            if self._connected:
                print(f"[MQTT] 已連線到 {self.broker}")
                return True
            else:
                print("[MQTT] 連線初始化完成，但狀態不確定")
                return True
        
        except Exception as e:
            self._connected = False
            print("[MQTT] 連線失敗: {}: {}".format(type(e).__name__, e))
            return False
    
    
    async def wait_connected(self, timeout_sec=30):
        """
        等待 MQTT 已連線
        
        參數:
            timeout_sec: 超時時間（秒）
        
        返回: True 連線成功，False 超時
        """
        try:
            await uasyncio.wait_for(self._connected_event.wait(), timeout_sec)
            return True
        except uasyncio.TimeoutError:
            print("[MQTT] 等待連線超時")
            return False
    
    
    async def publish(self, topic, message, qos=0):
        """
        發佈 MQTT 訊息
        
        參數:
            topic: 主題（str 或 bytes）
            message: 訊息內容（str 或 bytes）
            qos: QoS 級別（0 或 1）
        
        返回: True 發佈成功，False 失敗
        """
        try:
            # 確保 topic 和 message 是正確的格式
            if isinstance(topic, str):
                topic = topic.encode()
            if isinstance(message, str):
                message = message.encode()
            
            await self.client.publish(topic, message, qos=qos)
            print(f"[MQTT] 已發佈: {topic.decode() if isinstance(topic, bytes) else topic}")
            return True
        
        except Exception as e:
            print(f"[MQTT] 發佈失敗: {e}")
            return False
    
    
    async def subscribe(self, topic, qos=0, callback=None):
        """
        訂閱 MQTT 主題
        
        參數:
            topic: 主題（str 或 bytes）
            qos: QoS 級別（0 或 1）
            callback: 訂閱回調函數（可選）
        
        返回: True 訂閱成功，False 失敗
        """
        try:
            # 確保 topic 是正確的格式
            if isinstance(topic, str):
                topic = topic.encode()
            
            await self.client.subscribe(topic, qos=qos)
            print(f"[MQTT] 已訂閱: {topic.decode() if isinstance(topic, bytes) else topic}")
            return True
        
        except Exception as e:
            print(f"[MQTT] 訂閱失敗: {e}")
            return False
    
    
    async def disconnect(self):
        """
        斷線連接
        """
        try:
            await self.client.disconnect()
            self._connected = False
            print("[MQTT] 已斷線")
        except Exception as e:
            print(f"[MQTT] 斷線失敗: {e}")
    
    
    async def on_connected(self, client):
        """
        MQTT 連線成功回調
        """
        self._connected = True
        self._connected_event.set()
        print("[MQTT] 已連線成功")
    
    
    async def on_message(self, topic, msg, retained, properties=None):
        """
        MQTT 訊息接收回調
        """
        msg_str = msg.decode() if isinstance(msg, bytes) else msg
        topic_str = topic.decode() if isinstance(topic, bytes) else topic
        print(f"[MQTT] 收到訊息: {topic_str} = {msg_str}")
    
    
    def is_connected(self):
        """
        檢查連線狀態
        
        返回: True 已連線，False 未連線
        """
        return self._connected
