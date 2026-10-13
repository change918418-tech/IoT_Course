"""
hardware/sensors.py - 感測器模組
DHT11 溫濕度感測器 + TEMT 光感測器
"""

from machine import Pin, ADC
import dht
import config


class PirSensor:
    """PIR 高電位表示感測模組輸出移動訊號。"""
    def __init__(self):
        pin = getattr(config, 'PIR_PIN', 4)
        self.pin = Pin(pin, Pin.IN)
        print(f'[PIR] 初始化成功，GPIO={pin}，目前電位={self.pin.value()}')

    def is_motion(self):
        return bool(self.pin.value())


class Dht11Sensor:
    """DHT11 溫濕度感測器控制類別"""
    
    def __init__(self):
        """初始化 DHT11 感測器"""
        self.sensor = dht.DHT11(Pin(config.DHT11_PIN))
        self.temperature = 0.0
        self.humidity = 0.0
    
    def measure(self):
        """
        執行一次量測
        返回: (temperature, humidity) 元組，或在異常時返回 None
        """
        try:
            self.sensor.measure()
            self.temperature = self.sensor.temperature()
            self.humidity = self.sensor.humidity()
            return (self.temperature, self.humidity)
        except Exception as e:
            print(f"DHT11 量測錯誤: {e}")
            self.temperature = -1
            self.humidity = -1
            return (self.temperature, self.humidity)
    
    def get_data(self):
        """取得最後一次成功量測的資料"""
        return (self.temperature, self.humidity)
    
    def __str__(self):
        return f"溫度: {self.temperature}℃, 濕度: {self.humidity}%"


class LightSensor:
    """光感測器（可見光感測模組）控制類別"""
    
    def __init__(self):
        """初始化光感測器（ADC）"""
        self.adc = ADC(Pin(config.TEMT_ADC_PIN))
        # ESP32 ADC 預設 12-bit（0~4095），可根據實際調整
        self.adc.atten(ADC.ATTN_11DB)  # 設定衰減使用 0~3.3V 範圍
        self.current_value = 0
    
    def read(self):
        """
        讀取光線亮度值
        返回: ADC 原始值（0~4095）
        """
        try:
            self.current_value = self.adc.read()
            return self.current_value
        except Exception as e:
            print(f"光感測器讀取錯誤: {e}")
            return self.current_value
    
    def is_dark(self, threshold=None):
        """
        判斷環境是否黑暗
        返回: True 表示黑暗，False 表示明亮
        """
        if threshold is None:
            threshold = getattr(config, 'LIGHT_ALERT_TRIGGER_ADC', 1000)
        return self.read() < threshold
    
    def is_bright(self, threshold=None):
        """
        判斷環境是否明亮
        返回: True 表示明亮，False 表示黑暗
        """
        if threshold is None:
            threshold = getattr(config, 'LIGHT_ALERT_RESET_ADC', 1100)
        return self.read() > threshold
    
    def get_brightness_percent(self):
        """
        取得亮度百分比（假設 ADC 滿值為 4095）
        返回: 0~100 的百分比值
        """
        return int((self.current_value / 4095.0) * 100)
    
    def __str__(self):
        return f"光線亮度: {self.current_value} (約 {self.get_brightness_percent()}%)"
