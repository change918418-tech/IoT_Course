"""Owner admission, outcomes, rendering and producer integration with fake time."""
import ast
import asyncio
import importlib.util
import json
import random
import sys
import types
import unittest
from unittest.mock import patch
from test_led_control import ROOT, FakePin
import config


class StopCycles(BaseException):
    pass


def load_task(name, **namespace):
    tree = ast.parse((ROOT / 'tasks.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    namespace['config'] = config
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'tasks.py', 'exec'), namespace)
    return namespace[name]


class Hardware:
    def __init__(self):
        self.frames = []
    def write(self, value):
        if not self.frames or self.frames[-1] != value:
            self.frames.append(value)


class Clock:
    period = 1 << 30
    now = 0
    def ticks_ms(self):
        return self.now
    def ticks_diff(self, a, b):
        return ((a-b+self.period//2) % self.period) - self.period//2


class OwnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch.dict(sys.modules, {'uasyncio': asyncio}):
            spec = importlib.util.spec_from_file_location('owner_test', ROOT / 'services/led_service.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.module.get_current_time = lambda: ('2026/10/12', '一', '12:00:00')
        self.hw = Hardware()
        self.clock = Clock()
        self.service = self.module.LedService(self.hw, self.clock)

    async def test_relative_commands_not_merged_or_applied_by_producers(self):
        a = self.service.submit('cycle', 'button1')
        b = self.service.submit('cycle', 'web')
        self.assertEqual(self.hw.frames, [])
        self.assertEqual(self.service.snapshot()['color_index'], 7)
        self.service._step(0)
        self.assertEqual(self.hw.frames, [0, 1])
        for receipt in (a, b):
            self.assertEqual(self.service.result(receipt['id'])['status'], 'executed')

    async def test_alert_invalidates_pending_and_rejects_all_new_commands(self):
        pending = self.service.submit('cycle', 'web')
        alert = self.service.submit('low_light_alert', 'light')
        self.assertTrue(self.service.busy)  # Before owner is scheduled.
        self.assertEqual(self.service.result(pending['id'])['reason'], 'alert_started')
        for kind in ['cycle', 'set_color', 'low_light_alert']:
            self.assertEqual(self.service.submit(kind, 'test', 2)['reason'], 'busy')
        self.service._step(0)
        for i in range(1, 11):
            self.service._step(i*300)
        self.assertEqual(self.hw.frames, [4, 0]*5 + [7])
        self.assertFalse(self.service.busy)
        self.assertEqual(self.service.result(alert['id'])['status'], 'executed')
        self.service._step(3020)
        self.assertEqual(self.service.snapshot()['color_index'], 7)

    async def test_off_restore_wrap_and_no_skipped_phases_after_delay(self):
        self.service.submit('set_color', 'test', 0)
        self.service._step(0)
        self.clock.now = self.clock.period-100
        self.service.submit('low_light_alert', 'light')
        self.service._step(self.clock.now)
        self.service._step(200)  # 300 ms across wrap -> one falling edge.
        self.assertEqual(self.hw.frames[-1], 0)
        self.service._step(5000)  # Long delay -> only one new rising edge.
        self.assertEqual(self.service._effect['completed'], 1)
        for now in range(5300, 7701, 300):
            self.service._step(now)
        self.assertFalse(self.service.busy)
        self.assertFalse(self.service.snapshot()['is_on'])
        self.assertEqual(self.hw.frames[-1], 0)
        flash_snapshot = self.service.snapshot()
        self.assertEqual(flash_snapshot['alert_flash_count'], 1)
        self.assertEqual([item['sequence'] for item in flash_snapshot['alert_flash_log']], [1])
        self.assertTrue(all(item['time'] == '2026/10/12 12:00:00' for item in flash_snapshot['alert_flash_log']))

    async def test_capacity_frame_limit_invalid_input_and_bounded_history(self):
        for _ in range(8):
            self.assertEqual(self.service.submit('cycle', 'test')['status'], 'accepted')
        self.assertEqual(self.service.submit('cycle', 'test')['reason'], 'queue_full')
        self.service._step(0)
        self.assertEqual(self.service.snapshot()['queue_depth'], 4)
        self.assertEqual(self.service.submit('set_color', 'test', 8)['reason'], 'invalid_color')
        self.assertEqual(self.service.submit('unknown', 'test')['reason'], 'invalid_command')
        for _ in range(30):
            self.service.submit('unknown', 'test')
        self.assertEqual(len(self.service._results), 16)
        self.assertIsNone(self.service.result(1))
        # Alert is admissible even when ordinary command capacity is full.
        for _ in range(4):
            self.service.submit('cycle', 'test')
        self.assertEqual(self.service.submit('low_light_alert', 'light')['status'], 'accepted')

    async def test_owner_shutdown_and_cancel_only_owner_writes(self):
        for cancel in [False, True]:
            service = self.module.LedService(Hardware(), self.clock)
            reached, release = asyncio.Event(), asyncio.Event()
            async def sleep(_):
                reached.set()
                await release.wait()
            self.module.uasyncio = types.SimpleNamespace(sleep_ms=sleep, Event=asyncio.Event)
            alert = service.submit('low_light_alert', 'light')
            running = asyncio.create_task(service.run())
            await asyncio.wait_for(reached.wait(), 1)
            if cancel:
                running.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await running
            else:
                service.request_stop()
                self.assertEqual(service._hardware.frames[-1], 4)
                release.set()
                await asyncio.wait_for(running, 1)
            self.assertEqual(service._hardware.frames[-1], 0)
            self.assertFalse(service.snapshot()['available'])
            self.assertEqual(service.result(alert['id'])['status'], 'cancelled')
            self.assertEqual(service.submit('cycle', 'web')['reason'], 'stopped')

    async def test_light_hysteresis_and_button_press_consumption(self):
        trigger = config.LIGHT_ALERT_TRIGGER_ADC
        reset = config.LIGHT_ALERT_RESET_ADC
        readings = iter([trigger - 1, trigger, (trigger + reset) // 2, reset, reset - 1, trigger - 1])
        count = 0
        receipts = []
        async def sleep(_):
            nonlocal count
            count += 1
            if self.service.busy:
                receipts.append(self.service._queue[0][2]['id'])
                self.service._step(0)
                for i in range(1, 11):
                    self.service._step(i*300)
            if count == 6:
                raise StopCycles()
        run = load_task('light_sensor_task', uasyncio=types.SimpleNamespace(sleep_ms=sleep))
        with self.assertRaises(StopCycles):
            await run(types.SimpleNamespace(read=lambda: next(readings)), self.service)
        self.assertEqual(len(receipts), 2)
        alert_snapshot = self.service.snapshot()
        self.assertEqual(alert_snapshot['alert_flash_count'], 2)
        self.assertEqual([item['sequence'] for item in alert_snapshot['alert_flash_log']], [1, 2])
        owner = self.service
        class Button:
            count = 0
            press_rejected = False
            async def wait_press(self, reject_if=None):
                self.count += 1
                self.press_rejected = self.count == 1
            async def wait_release(self):
                if self.count == 2:
                    raise StopCycles()
        async def no_sleep(_):
            pass
        run = load_task('button1_task', uasyncio=types.SimpleNamespace(sleep_ms=no_sleep, sleep=no_sleep))
        with self.assertRaises(StopCycles):
            await run(Button(), owner, asyncio.Event())
        self.assertEqual(len(owner._queue), 1)

    async def test_web_acceptance_rejection_result_and_expiry(self):
        sys.path.insert(0, str(ROOT/'lib'))
        try:
            with patch.dict(sys.modules, {'network': types.ModuleType('network'), 'uasyncio': asyncio}):
                spec = importlib.util.spec_from_file_location('web_owner_test', ROOT/'web_server.py')
                web = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(web)
            web.led_service = self.service
            from microdot.test_client import TestClient
            client = TestClient(web.app)
            web.get_current_light = lambda: (_ for _ in ()).throw(AssertionError('Status must not sample ADC'))
            fast_status = await client.get('/api/led/status')
            self.assertEqual(fast_status.status_code, 200)
            self.assertFalse(fast_status.json['alert_active'])
            self.assertEqual(fast_status.headers['Cache-Control'], 'no-store')
            http_response = await client.post('/api/led/toggle')
            self.assertEqual(http_response.status_code, 202)
            http_id = http_response.json['id']
            response = await web.api_led_toggle(None)
            self.assertEqual(response.status_code, 202)
            receipt = json.loads(response.body)
            self.assertEqual(receipt['status'], 'accepted')
            self.service.submit('low_light_alert', 'light')
            self.assertTrue((await client.get('/api/led/status')).json['alert_active'])
            http_result = await client.get('/api/led/commands/{}'.format(http_id))
            self.assertEqual(http_result.status_code, 200)
            self.assertEqual(http_result.json['status'], 'rejected')
            result = json.loads((await web.api_led_command_result(None, receipt['id'])).body)
            self.assertEqual(result['status'], 'rejected')
            self.assertEqual((await web.api_led_toggle(None)).status_code, 409)
            self.assertEqual((await web.api_led_command_result(None, 9999)).status_code, 404)
            for i in range(11):
                self.service._step(i*300)
            new = json.loads((await web.api_led_toggle(None)).body)
            self.service._step(3020)
            result = json.loads((await web.api_led_command_result(None, new['id'])).body)
            self.assertEqual(result['status'], 'executed')
            for _ in range(8):
                self.service.submit('cycle', 'test')
            self.assertEqual((await client.post('/api/led/toggle')).status_code, 429)
        finally:
            sys.path.remove(str(ROOT/'lib'))

    async def test_output_failure_reports_failed_and_owner_stops(self):
        class BrokenHardware:
            def write(self, value):
                if value != 0:
                    raise OSError('fake GPIO failure')
        service = self.module.LedService(BrokenHardware(), self.clock)
        receipt = service.submit('set_color', 'web', 2)
        with self.assertRaises(OSError):
            await service.run()
        self.assertEqual(service.result(receipt['id'])['status'], 'failed')
        self.assertEqual(service.snapshot()['error'], 'fake GPIO failure')
        self.assertTrue(service._stopped.is_set())

    async def test_real_button_latches_busy_through_debounce(self):
        class Pin(FakePin):
            IN, PULL_UP = 0, 1
            def __init__(self, *args):
                self.level = 0
                self.writes = 0
        busy = True
        async def sleep(_):
            nonlocal busy
            busy = False
        with patch.dict(sys.modules, {'machine': types.SimpleNamespace(Pin=Pin),
                'uasyncio': types.SimpleNamespace(sleep_ms=sleep)}):
            spec = importlib.util.spec_from_file_location('owner_button_test', ROOT/'hardware/button.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        button = module.Button(17)
        await button.wait_press(reject_if=lambda: busy)
        self.assertTrue(button.press_rejected)
        button.pin.value(1)
        await button.wait_release()
        button.pin.value(0)
        await button.wait_press(reject_if=lambda: busy)
        self.assertFalse(button.press_rejected)

    async def test_deterministic_mixed_commands_remain_bounded_and_finish(self):
        random_source = random.Random(42)
        for frame in range(1000):
            for _ in range(random_source.randrange(4)):
                kind = random_source.choice(['cycle', 'cycle', 'set_color', 'low_light_alert'])
                self.service.submit(kind, 'stress', random_source.randrange(8))
            self.service._step(frame*20)
            self.assertLessEqual(len(self.service._queue), 8)
            self.assertLessEqual(len(self.service._results), 16)
            self.assertIn(self.service.snapshot()['color_index'], range(8))
        for frame in range(1000, 1200):
            self.service._step(frame*20)
        self.assertFalse(self.service.busy)
        self.assertEqual(self.service.snapshot()['queue_depth'], 0)
        self.assertTrue(all(value in range(8) for value in self.hw.frames))

    async def test_actual_main_error_path_waits_for_owner_to_turn_off(self):
        class Mqtt:
            async def disconnect(self):
                pass
        async def initialize():
            return self.hw, None, None, None, None, Mqtt(), None, {}, None, None
        async def fail(*args):
            await asyncio.sleep(0)
            raise RuntimeError('fake task failure')
        async def idle(*args):
            await asyncio.Event().wait()
        async def sleep_ms(_):
            await asyncio.sleep(0)
        self.module.uasyncio = types.SimpleNamespace(Event=asyncio.Event, sleep_ms=sleep_ms)
        task_names = ['button2_task', 'dht11_read_task', 'light_sensor_task', 'rfid_read_task', 'pir_monitor_task',
                      'music_on_motion_task', 'oled_display_task', 'mqtt_publish_task', 'mqtt_subscribe_task']
        task_adapter = types.SimpleNamespace(**{name: idle for name in task_names}, button1_task=fail)
        web = types.SimpleNamespace(web_server_task=idle, sensor_monitor_task=idle)
        tree = ast.parse((ROOT/'main.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'main')
        from hardware.motion import new_motion_state
        namespace = dict(initialize_system=initialize, uasyncio=asyncio, tasks=task_adapter,
            web_server=web, new_motion_state=new_motion_state,
            LedService=lambda hw: self.module.LedService(hw, self.clock))
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
        with self.assertRaises(RuntimeError):
            await asyncio.wait_for(namespace['main'](), 1)
        self.assertEqual(self.hw.frames[-1], 0)
        self.assertFalse(web.led_service.snapshot()['available'])
