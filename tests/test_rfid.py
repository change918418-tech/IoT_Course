"""Desktop fake RFID tests; do not validate physical SPI or card presence."""
import ast
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config
from hardware.rfid import RfidReader, new_rfid_state


class StopCycles(BaseException):
    pass


class RfidTests(unittest.TestCase):
    def test_driver_protocol_and_full_sample_format(self):
        class Driver:
            OK = 0
            REQIDL = 0x26
            def __init__(self, **pins):
                self.pins = pins
                self.stat = self.OK
                self.anticoll_stat = self.OK
                self.calls = []
            async def request(self, mode):
                self.calls.append(mode)
                return self.stat, 16
            async def anticoll(self):
                return self.anticoll_stat, [0x01, 0x02, 0x03, 0x04, 0x04]
        driver_module = types.ModuleType('mfrc522_async')
        driver_module.MFRC522Async = Driver
        tools = types.ModuleType('aiot_tools')
        tools.to_hex_string = lambda values: ''.join('{:02X}'.format(v) for v in values)
        with patch.dict(sys.modules, {'mfrc522_async': driver_module, 'aiot_tools': tools}):
            reader = RfidReader()
        self.assertEqual(reader.reader.pins, dict(sck=12, mosi=11, miso=10, rst=9, cs=13))
        self.assertEqual(asyncio.run(reader.read_uid()), '0102030404')
        self.assertEqual(reader.reader.calls, [Driver.REQIDL])
        reader.reader.stat = 2
        self.assertIsNone(asyncio.run(reader.read_uid()))
        reader.reader.stat = 0
        reader.reader.anticoll_stat = 2
        with self.assertRaises(RuntimeError):
            asyncio.run(reader.read_uid())

    def test_task_retains_last_read_and_recovers(self):
        tree = ast.parse((ROOT / 'tasks.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'rfid_read_task')
        state = new_rfid_state()
        snapshots = []
        values = iter(['0102030404', None, RuntimeError('bad "card"'), 'AABBCCDDEE'])
        class Reader:
            async def read_uid(self):
                value = next(values)
                if isinstance(value, Exception):
                    raise value
                return value
        async def sleep(ms):
            self.assertEqual(ms, config.RFID_POLL_INTERVAL_MS)
            snapshots.append(dict(state))
            if len(snapshots) == 4:
                raise StopCycles()
        namespace = dict(config=config, uasyncio=types.SimpleNamespace(sleep_ms=sleep),
                         get_current_time=lambda: ('2026-10-06', '二', '00:30:00'))
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'tasks.py', 'exec'), namespace)
        with self.assertRaises(StopCycles):
            asyncio.run(namespace['rfid_read_task'](Reader(), state))
        self.assertEqual(snapshots[0]['last_uid'], '0102030404')
        self.assertEqual(snapshots[1], snapshots[0])
        self.assertEqual(snapshots[2]['status'], 'read_error')
        self.assertEqual(snapshots[2]['last_uid'], '0102030404')
        self.assertEqual(state['status'], 'ready')
        self.assertIsNone(state['error'])
        self.assertEqual(state['last_uid'], 'AABBCCDDEE')
        self.assertEqual([item['uid'] for item in state['recent_reads']], ['0102030404', 'AABBCCDDEE'])
        self.assertIsNone(new_rfid_state()['last_uid'])

    def test_task_limits_recent_reads_to_five(self):
        values = iter(['000000000' + str(index) for index in range(1, 7)])
        state = new_rfid_state()
        cycles = 0
        async def sleep(_):
            nonlocal cycles
            cycles += 1
            if cycles == 6:
                raise StopCycles()
        class Reader:
            async def read_uid(self):
                return next(values)
        namespace = dict(config=config, uasyncio=types.SimpleNamespace(sleep_ms=sleep),
                         get_current_time=lambda: ('2026-10-06', '二', '00:30:00'))
        tree = ast.parse((ROOT / 'tasks.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'rfid_read_task')
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'tasks.py', 'exec'), namespace)
        with self.assertRaises(StopCycles):
            asyncio.run(namespace['rfid_read_task'](Reader(), state))
        self.assertEqual([item['uid'] for item in state['recent_reads']],
                         ['0000000002', '0000000003', '0000000004', '0000000005', '0000000006'])

    def test_api_serializes_cache_null_zero_and_quotes(self):
        sys.path.insert(0, str(ROOT / 'lib'))
        try:
            with patch.dict(sys.modules, {'network': types.ModuleType('network'), 'uasyncio': asyncio,
                                             'machine': types.SimpleNamespace(Pin=lambda *args: None)}):
                spec = importlib.util.spec_from_file_location('web_rfid_test', ROOT / 'web_server.py')
                web = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(web)
            web.rfid_state.update(status='read_error', last_uid='0102030404', error='bad "card"')
            web.sensor_snapshot = types.SimpleNamespace(snapshot=lambda: {
                'temperature': {'value': None, 'valid': False, 'quality': 'unavailable',
                                'age_ms': None, 'error': None, 'updated_at_ms': None},
                'humidity': {'value': None, 'valid': False, 'quality': 'unavailable',
                             'age_ms': None, 'error': None, 'updated_at_ms': None},
                'light': {'value': 0, 'valid': True, 'quality': 'good',
                          'age_ms': 0, 'error': None, 'updated_at_ms': 0},
                'sample_seq': 1,
                'status': 'partial',
            })
            web.light_sensor = None
            response = asyncio.run(web.api_data(None))
            body = response.body.decode() if isinstance(response.body, bytes) else response.body
            data = json.loads(body)
            self.assertIsNone(data['temp'])
            self.assertIsNone(data['humidity'])
            self.assertEqual(data['light'], 0)
            self.assertEqual(data['light_thresholds'], {
                'trigger': config.LIGHT_ALERT_TRIGGER_ADC,
                'reset': config.LIGHT_ALERT_RESET_ADC
            })
            self.assertEqual(data['rfid']['error'], 'bad "card"')
            self.assertEqual(data['rfid']['last_uid'], '0102030404')
            self.assertEqual(data['rfid']['recent_reads'], [])
            self.assertFalse(data['motion']['detected'])
            self.assertEqual(data['motion']['count'], 0)
            self.assertEqual(data['motion']['recent_detections'], [])
            self.assertIsNone(data['motion']['last_detected_at'])
            motion_response = asyncio.run(web.api_motion_status(None))
            motion_body = motion_response.body.decode() if isinstance(motion_response.body, bytes) else motion_response.body
            motion_data = json.loads(motion_body)
            self.assertEqual(motion_data['motion'] if 'motion' in motion_data else motion_data, data['motion'])
            self.assertEqual(motion_response.headers.get('Cache-Control'), 'no-store')
        finally:
            sys.path.remove(str(ROOT / 'lib'))


if __name__ == '__main__':
    unittest.main()
