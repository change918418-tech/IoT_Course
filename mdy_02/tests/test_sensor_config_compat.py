"""Import the actual sensor module with legacy device configuration."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class SensorConfigCompatTests(unittest.TestCase):
    def test_missing_alert_keys_import_defaults_and_explicit_threshold(self):
        class ADC:
            ATTN_11DB = 3
            def __init__(self, pin):
                self.value = 999
            def atten(self, value):
                pass
            def read(self):
                return self.value
        legacy = types.ModuleType('config')
        legacy.TEMT_ADC_PIN = 8
        machine = types.SimpleNamespace(Pin=lambda *args: None, ADC=ADC)
        root = Path(__file__).resolve().parents[1]
        with patch.dict(sys.modules, {'config': legacy, 'machine': machine,
                                     'dht': types.ModuleType('dht')}):
            spec = importlib.util.spec_from_file_location('legacy_sensor_test', root / 'hardware/sensors.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # Previously raised AttributeError here.
        sensor = module.LightSensor()
        self.assertTrue(sensor.is_dark())
        self.assertFalse(sensor.is_dark(threshold=900))
        sensor.adc.value = 1101
        self.assertTrue(sensor.is_bright())
        self.assertFalse(sensor.is_bright(threshold=1200))
        legacy.LIGHT_ALERT_TRIGGER_ADC = 1200
        self.assertTrue(sensor.is_dark())
