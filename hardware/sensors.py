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
    """DHT11 driver; failed reads retain the last valid value."""

    def __init__(self):
        self.sensor = dht.DHT11(Pin(config.DHT11_PIN))
        self.temperature = None
        self.humidity = None
        self.last_error = None

    def measure(self):
        """Return a valid (temperature, humidity) tuple or None on failure."""
        try:
            self.sensor.measure()
            self.temperature = self.sensor.temperature()
            self.humidity = self.sensor.humidity()
            self.last_error = None
            return (self.temperature, self.humidity)
        except Exception as e:
            self.last_error = str(e)
            print(f"DHT11 量測錯誤: {e}")
            return None

    def get_data(self):
        """Return the last valid tuple, or (None, None) before first success."""
        return (self.temperature, self.humidity)

    def __str__(self):
        return f"溫度: {self.temperature}℃, 濕度: {self.humidity}%"

class LightSensor:
    """光感測器（可見光感測模組）控制類別"""

    def __init__(self):
        self.adc = ADC(Pin(config.TEMT_ADC_PIN))
        self.adc.atten(ADC.ATTN_11DB)
        self.current_value = None
        self.last_error = None

    def read(self):
        """讀取光線亮度值；失敗時保留最後有效值。"""
        try:
            self.current_value = self.adc.read()
            self.last_error = None
            return self.current_value
        except Exception as e:
            self.last_error = str(e)
            print(f"光感測器讀取錯誤: {e}")
            return self.current_value

    def is_dark(self, threshold=None):
        if threshold is None:
            threshold = getattr(config, 'LIGHT_ALERT_TRIGGER_ADC', 1000)
        value = self.read()
        if value is None:
            return False
        if getattr(config, 'LIGHT_DARK_WHEN_HIGH', False):
            return value > threshold
        return value < threshold

    def is_bright(self, threshold=None):
        if threshold is None:
            threshold = getattr(config, 'LIGHT_ALERT_RESET_ADC', 1100)
        value = self.read()
        if value is None:
            return False
        if getattr(config, 'LIGHT_DARK_WHEN_HIGH', False):
            return value <= threshold
        return value > threshold

    def get_brightness_percent(self):
        if self.current_value is None:
            return None
        return int((self.current_value / 4095.0) * 100)

    def __str__(self):
        return f"光線亮度: {self.current_value} (約 {self.get_brightness_percent()}%)"
