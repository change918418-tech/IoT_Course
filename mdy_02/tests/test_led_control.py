"""GPIO adapter tests; policy lives in LedService."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
class FakePin:
    OUT = 1
    def __init__(self, number, mode):
        self.level = 0
        self.writes = 0
    def value(self, level=None):
        if level is not None:
            self.level = level
            self.writes += 1
        return self.level

class LedControlTests(unittest.TestCase):
    def test_boot_off_all_eight_colors_and_unchanged_render(self):
        with patch.dict(sys.modules, {'machine': types.SimpleNamespace(Pin=FakePin)}):
            spec = importlib.util.spec_from_file_location('gpio_led_test', ROOT / 'hardware/led.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        led = module.RgbLed()
        for index in range(8):
            led.write(index)
            output = (led.red.value() << 2) | (led.green.value() << 1) | led.blue.value()
            self.assertEqual(output, index)
            writes = led.red.writes
            led.write(index)
            self.assertEqual(led.red.writes, writes)
