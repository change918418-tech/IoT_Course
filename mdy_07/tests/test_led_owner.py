"""P1 LED controller and unified command boundary tests."""
import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class StopCycles(BaseException):
    pass


class Hardware:
    def __init__(self):
        self.frames = []

    def write(self, value):
        if not self.frames or self.frames[-1] != value:
            self.frames.append(value)


class Clock:
    period = 1 << 30

    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, a, b):
        return ((a - b + self.period // 2) % self.period) - self.period // 2


def load_owner():
    with patch.dict(sys.modules, {'uasyncio': asyncio}):
        spec = importlib.util.spec_from_file_location(
            'led_controller_test', ROOT / 'services' / 'led_controller.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def load_task(name, **namespace):
    import ast
    tree = ast.parse((ROOT / 'tasks.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body
                if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
                and n.name == name)
    namespace['config'] = __import__('config')
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'tasks.py', 'exec'), namespace)
    return namespace[name]


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = load_owner()
        self.module.get_current_time = lambda: ('2026/10/12', '一', '12:00:00')
        self.hw = Hardware()
        self.clock = Clock()
        self.controller = self.module.LedController(self.hw, self.clock, mode='AUTO')
        command_spec = importlib.util.spec_from_file_location(
            'command_service_test', ROOT / 'services' / 'command_service.py')
        self.command_module = importlib.util.module_from_spec(command_spec)
        command_spec.loader.exec_module(self.command_module)
        self.commands = self.command_module.CommandService(self.controller)

    async def test_all_sources_use_request_ids_and_apply_only_in_owner(self):
        button = self.commands.submit('cycle', 'button1')
        web = self.commands.submit('set_color', 'web', 4)
        mqtt = self.commands.submit('set_color', 'mqtt', 5)
        self.assertEqual([button['request_id'], web['request_id'], mqtt['request_id']], [1, 2, 3])
        self.assertEqual(self.hw.frames, [])
        self.controller._step(0)
        self.assertEqual(self.hw.frames, [0, 4, 5])
        self.assertEqual(self.commands.result(mqtt['request_id'])['status'], 'executed')
        self.assertEqual(self.controller.snapshot()['desired_color'], 5)
        self.assertEqual(self.controller.snapshot()['applied_output'], 5)

    async def test_auto_alert_restores_desired_color(self):
        self.commands.submit('set_color', 'web', 5)
        self.controller._step(0)
        alert = self.commands.submit('low_light_alert', 'light')
        self.assertEqual(
            self.commands.snapshot()['active_effect'],
            'low_light_alert')
        self.controller._step(0)
        for now in range(300, 3301, 300):
            self.controller._step(now)
        self.assertEqual(self.commands.result(alert['request_id'])['status'], 'executed')
        snapshot = self.controller.snapshot()
        self.assertEqual(snapshot['desired_color'], 5)
        self.assertEqual(snapshot['applied_output'], 5)
        self.assertFalse(snapshot['alert_active'])
        self.assertIsNone(snapshot['active_effect'])

    async def test_green_flash_runs_three_times_and_restores_normal_state(self):
        for initial_color in (0, 1, 2, 4):
            with self.subTest(initial_color=initial_color):
                hardware = Hardware()
                controller = self.module.LedController(
                    hardware, self.clock, mode='AUTO')
                commands = self.command_module.CommandService(controller)
                commands.submit('set_color', 'test', initial_color)
                controller._step(0)
                hardware.frames.clear()

                effect = commands.submit(
                    'green_flash_alert', 'button3')
                self.assertEqual(effect['status'], 'accepted')
                self.assertTrue(commands.busy)
                self.assertEqual(
                    commands.snapshot()['active_effect'],
                    'green_flash_alert')
                controller._step(1)
                for now in range(301, 1802, 300):
                    controller._step(now)

                expected = [2, 0, 2, 0, 2, 0]
                if initial_color != 0:
                    expected.append(initial_color)
                self.assertEqual(hardware.frames, expected)
                self.assertEqual(
                    commands.result(effect['request_id'])['status'],
                    'executed')
                snapshot = commands.snapshot()
                self.assertEqual(snapshot['desired_color'], initial_color)
                self.assertEqual(snapshot['applied_output'], initial_color)
                self.assertFalse(snapshot['alert_active'])
                self.assertIsNone(snapshot['active_effect'])
                self.assertEqual(snapshot['alert_flash_count'], 0)

    async def test_effects_reject_competing_effects_and_pending_changes(self):
        pending = self.commands.submit('cycle', 'button1')
        green = self.commands.submit('green_flash_alert', 'button3')
        self.assertEqual(green['status'], 'accepted')
        self.assertEqual(
            self.commands.result(pending['request_id'])['reason'],
            'alert_started')
        for kind, source in (
                ('cycle', 'button1'),
                ('green_flash_alert', 'button3'),
                ('low_light_alert', 'light')):
            rejected = self.commands.submit(kind, source)
            self.assertEqual(rejected['status'], 'rejected')
            self.assertEqual(rejected['reason'], 'busy')

        other = self.module.LedController(Hardware(), self.clock, mode='AUTO')
        other_commands = self.command_module.CommandService(other)
        self.assertEqual(
            other_commands.submit('low_light_alert', 'light')['status'],
            'accepted')
        rejected_green = other_commands.submit(
            'green_flash_alert', 'button3')
        self.assertEqual(rejected_green['reason'], 'busy')

    async def test_button3_submits_once_and_consumes_busy_press(self):
        class Button:
            def __init__(self):
                self.press_rejected = False
                self.releases = 0

            async def wait_press(self, reject_if=None):
                self.press_rejected = bool(reject_if and reject_if())

            async def wait_release(self):
                self.releases += 1
                raise StopCycles()

        task = load_task(
            'button3_task',
            uasyncio=types.SimpleNamespace(
                sleep_ms=lambda _: None, sleep=lambda _: None))
        button = Button()
        with self.assertRaises(StopCycles):
            await task(button, self.commands)
        self.assertEqual(button.releases, 1)
        self.assertEqual(self.controller._queue[0][0], 'green_flash_alert')
        self.assertEqual(self.controller._queue[0][2]['source'], 'button3')

        class BusyCommands:
            busy = True

            def submit(self, *args):
                raise AssertionError('busy press must not submit')

        busy_button = Button()
        with self.assertRaises(StopCycles):
            await task(busy_button, BusyCommands())
        self.assertTrue(busy_button.press_rejected)
        self.assertEqual(busy_button.releases, 1)

    async def test_green_flash_gpio_failure_marks_request_failed(self):
        class BrokenHardware:
            def write(self, value):
                if value != 0:
                    raise OSError('fake green GPIO failure')

        controller = self.module.LedController(
            BrokenHardware(), self.clock, mode='AUTO')
        commands = self.command_module.CommandService(controller)
        effect = commands.submit('green_flash_alert', 'button3')
        with self.assertRaises(OSError):
            await controller.run()
        result = commands.result(effect['request_id'])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'fake green GPIO failure')
        self.assertFalse(controller.busy)

    async def test_manual_mode_rejects_light_override(self):
        mode = self.commands.submit('set_mode', 'web', 'MANUAL')
        self.controller._step(0)
        self.assertEqual(self.commands.result(mode['request_id'])['status'], 'executed')
        rejected = self.commands.submit('low_light_alert', 'light')
        self.assertEqual(rejected['status'], 'rejected')
        self.assertEqual(rejected['reason'], 'manual_mode')

    async def test_queue_and_result_history_are_bounded(self):
        for _ in range(self.controller.capacity):
            self.assertEqual(self.commands.submit('cycle', 'button1')['status'], 'accepted')
        self.assertEqual(self.commands.submit('cycle', 'web')['reason'], 'queue_full')
        self.assertEqual(self.commands.submit('set_color', 'web', 8)['reason'], 'invalid_color')
        self.assertEqual(self.commands.submit('set_mode', 'web', 'UNKNOWN')['reason'], 'invalid_mode')
        for _ in range(30):
            self.commands.submit('unknown', 'test')
        self.assertLessEqual(len(self.controller._results), self.controller.result_capacity)
        self.assertLessEqual(len(self.controller._queue), self.controller.capacity)

    async def test_owner_failure_records_failed_result_and_stops(self):
        class BrokenHardware:
            def write(self, value):
                if value != 0:
                    raise OSError('fake GPIO failure')

        controller = self.module.LedController(BrokenHardware(), self.clock)
        commands = self.command_module.CommandService(controller)
        receipt = commands.submit('set_color', 'web', 2)
        with self.assertRaises(OSError):
            await controller.run()
        self.assertEqual(commands.result(receipt['request_id'])['status'], 'failed')
        self.assertEqual(controller.snapshot()['error'], 'fake GPIO failure')
        self.assertTrue(controller._stopped.is_set())

    async def test_light_producer_uses_command_service_and_snapshot(self):
        readings = iter([999, 1000])
        snapshots = []

        class Light:
            last_error = None
            def read(self):
                return next(readings)

        class Snapshot:
            def update_light(self, value, error=None):
                snapshots.append((value, error))

        async def sleep(_):
            raise StopCycles()

        config = __import__('config')
        task = load_task(
            'light_sensor_task',
            uasyncio=types.SimpleNamespace(sleep_ms=sleep))
        with patch.object(config, 'LIGHT_DARK_WHEN_HIGH', False, create=True), \
                patch.object(config, 'LIGHT_ALERT_TRIGGER_ADC', 1000):
            with self.assertRaises(StopCycles):
                await task(Light(), self.commands, Snapshot())
        self.assertEqual(snapshots[0], (999, None))
        self.assertEqual(self.controller._queue[0][2]['source'], 'light')

    async def test_high_adc_dark_mode_triggers_and_rearms(self):
        readings = iter([2700, 2600, 1110, 2700])
        submitted = []

        class Light:
            last_error = None
            def read(self):
                return next(readings)

        class Commands:
            def submit(self, kind, source):
                submitted.append((kind, source))
                return {'status': 'accepted'}

        calls = 0
        async def sleep(_):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise StopCycles()

        config = __import__('config')
        task = load_task(
            'light_sensor_task',
            uasyncio=types.SimpleNamespace(sleep_ms=sleep))
        with patch.object(config, 'LIGHT_DARK_WHEN_HIGH', True, create=True), \
                patch.object(config, 'LIGHT_ALERT_TRIGGER_ADC', 2200), \
                patch.object(config, 'LIGHT_ALERT_RESET_ADC', 1600):
            with self.assertRaises(StopCycles):
                await task(Light(), Commands())
        self.assertEqual(submitted, [
            ('low_light_alert', 'light'),
            ('low_light_alert', 'light'),
        ])

    async def test_light_error_does_not_submit_alert(self):
        class Light:
            last_error = 'adc failure'
            def read(self):
                return __import__('config').LIGHT_ALERT_TRIGGER_ADC - 1

        class Snapshot:
            def update_light(self, value, error=None):
                self.observed = (value, error)

        async def sleep(_):
            raise StopCycles()

        task = load_task(
            'light_sensor_task',
            uasyncio=types.SimpleNamespace(sleep_ms=sleep))
        with self.assertRaises(StopCycles):
            await task(Light(), self.commands, Snapshot())
        self.assertEqual(self.controller.snapshot()['queue_depth'], 0)

    async def test_web_apis_use_command_service_and_cached_snapshot(self):
        sys.path.insert(0, str(ROOT / 'lib'))
        try:
            with patch.dict(sys.modules, {
                'network': types.ModuleType('network'),
                'uasyncio': asyncio,
            }):
                spec = importlib.util.spec_from_file_location(
                    'web_owner_test', ROOT / 'web_server.py')
                web = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(web)
            web.command_service = self.commands
            web.sensor_snapshot = types.SimpleNamespace(snapshot=lambda: {
                'temperature': {'value': 25, 'valid': True, 'quality': 'good', 'age_ms': 1},
                'humidity': {'value': 60, 'valid': True, 'quality': 'good', 'age_ms': 1},
                'light': {'value': 0, 'valid': True, 'quality': 'good', 'age_ms': 1},
                'sample_seq': 3,
                'status': 'ready',
            })
            from microdot.test_client import TestClient
            client = TestClient(web.app)
            response = await client.post('/api/led/toggle')
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json['source'], 'web')
            status = await client.get('/api/led/status')
            self.assertEqual(status.headers['Cache-Control'], 'no-store')
            data = await client.get('/api/data')
            body = json.loads(data.body)
            self.assertEqual(body['light'], 0)
            self.assertEqual(body['sensor']['status'], 'ready')
            canonical = await client.post(
                '/api/led/commands', body={'kind': 'set_color', 'value': 4})
            self.assertEqual(canonical.status_code, 202)
            command_id = canonical.json['request_id']
            result = await client.get('/api/led/commands/{}'.format(command_id))
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['source'], 'web')
            self.assertEqual(result.json['kind'], 'set_color')
            self.assertEqual(
                (await client.post('/api/led/mode',
                                   body={'mode': 'MANUAL'})).status_code, 202)
        finally:
            sys.path.remove(str(ROOT / 'lib'))


if __name__ == '__main__':
    unittest.main()
