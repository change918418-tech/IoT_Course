import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class MqttTests(unittest.TestCase):
    def test_connect_reports_socket_error_without_traceback_module(self):
        fake_uasyncio = types.ModuleType('uasyncio')
        fake_uasyncio.Event = asyncio.Event
        fake_uasyncio.sleep = asyncio.sleep
        fake_mqtt_as = types.ModuleType('mqtt_as')
        fake_mqtt_as.config = {}
        fake_mqtt_as.MQTTClient = lambda _config: types.SimpleNamespace()
        with patch.dict(sys.modules, {'uasyncio': fake_uasyncio, 'mqtt_as': fake_mqtt_as}):
            spec = importlib.util.spec_from_file_location(
                'mqtt_client_test', ROOT / 'communication' / 'mqtt_client.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        class FailingClient:
            async def connect(self):
                raise OSError(104, 'ECONNRESET')

        manager = module.MqttManager('ssid', 'password')
        manager.client = FailingClient()
        self.assertFalse(asyncio.run(manager.connect()))
        self.assertFalse(manager.is_connected())


if __name__ == '__main__':
    unittest.main()
