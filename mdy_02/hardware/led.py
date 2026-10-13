"""GPIO adapter. After initialization, only LedService.run writes this object."""
from machine import Pin
import config


class RgbLed:
    def __init__(self):
        self.red = Pin(config.LED_RED_PIN, Pin.OUT)
        self.green = Pin(config.LED_GREEN_PIN, Pin.OUT)
        self.blue = Pin(config.LED_BLUE_PIN, Pin.OUT)
        self._output = None
        self.write(0)  # Bootstrap safety; owner has not started yet.

    def write(self, index):
        if index == self._output:
            return
        self.red.value((index >> 2) & 1)
        self.green.value((index >> 1) & 1)
        self.blue.value(index & 1)
        self._output = index
