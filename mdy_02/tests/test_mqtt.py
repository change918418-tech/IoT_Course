import ast
import asyncio
import importlib.util
import json
from pathlib import Path
import inspect
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_mqtt_module():
    fake_uasyncio = types.ModuleType('uasyncio')
    for name in ('Event', 'TimeoutError', 'wait_for', 'sleep', 'create_task'):
        setattr(fake_uasyncio, name, getattr(asyncio, name))

    class FakeClient:
        instances = []

        def __init__(self, mqtt_config):
            self.config = mqtt_config
            self.connected = False
            self.subscriptions = []
            self.published = []
            FakeClient.instances.append(self)

        async def connect(self):
            self.connected = True
            callback = self.config.get('connect_coro')
            if callback:
                await callback(self)

        def isconnected(self):
            return self.connected

        async def subscribe(self, topic, qos=0):
            self.subscriptions.append((topic, qos))

        async def publish(self, topic, message, qos=0):
            self.published.append((topic, message, qos))

        async def disconnect(self):
            self.connected = False

    fake_mqtt_as = types.ModuleType('mqtt_as')
    fake_mqtt_as.config = {}
    fake_mqtt_as.MQTTClient = FakeClient
    with patch.dict(sys.modules, {
        'uasyncio': fake_uasyncio,
        'mqtt_as': fake_mqtt_as,
    }):
        spec = importlib.util.spec_from_file_location(
            'mqtt_client_test', ROOT / 'communication' / 'mqtt_client.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module, FakeClient


def load_task(name, **namespace):
    tree = ast.parse((ROOT / 'tasks.py').read_text(encoding='utf-8'))
    node = next(
        n for n in tree.body
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
        and n.name == name)
    namespace.setdefault('config', __import__('config'))
    exec(compile(ast.Module(body=[node], type_ignores=[]),
                 'tasks.py', 'exec'), namespace)
    return namespace[name]


class StopTask(BaseException):
    pass


class MqttManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_requires_connect_callback_confirmation(self):
        module, _ = load_mqtt_module()
        class SilentClient:
            async def connect(self):
                pass

        manager = module.MqttManager('ssid', 'password')
        manager.client = SilentClient()
        manager.CONNECT_CONFIRM_TIMEOUT_SEC = 0.001

        self.assertFalse(await manager.wait_connected(0.001))
        self.assertFalse(await manager.connect())
        self.assertFalse(manager.is_connected())

    async def test_connect_and_wait_connected_use_confirmed_state(self):
        module, FakeClient = load_mqtt_module()
        manager = module.MqttManager('ssid', 'password')

        self.assertTrue(await manager.connect())
        self.assertTrue(manager.is_connected())
        self.assertEqual(len(FakeClient.instances), 1)

    async def test_synchronous_callback_dispatches_registered_handler(self):
        module, FakeClient = load_mqtt_module()
        manager = module.MqttManager('ssid', 'password')
        FakeClient.instances[0].connected = True
        await manager.on_connected(FakeClient.instances[0])

        received = []

        def handler(topic, message, retained):
            received.append((topic, message, retained))

        self.assertTrue(await manager.subscribe(
            'cmd', qos=0, callback=handler))
        callback = FakeClient.instances[0].config['subs_cb']
        callback(b'cmd', b'led:4', False)

        self.assertEqual(received, [(b'cmd', b'led:4', False)])
        self.assertFalse(inspect.iscoroutinefunction(manager.on_message))

    async def test_publish_request_has_separate_result_state(self):
        module, FakeClient = load_mqtt_module()
        manager = module.MqttManager('ssid', 'password')
        FakeClient.instances[0].connected = True
        await manager.on_connected(FakeClient.instances[0])
        event = asyncio.Event()

        accepted = manager.request_publish(event)
        self.assertEqual(accepted['status'], 'accepted')
        self.assertEqual(accepted['request_id'], 1)
        self.assertTrue(event.is_set())

        manager.mark_publish_started()
        self.assertEqual(manager.publish_status()['status'], 'publishing')
        manager.mark_publish_finished(True)
        self.assertEqual(manager.publish_status()['status'], 'published')

    async def test_publish_request_reports_unavailable_without_connection(self):
        module, _ = load_mqtt_module()
        manager = module.MqttManager('ssid', 'password')
        event = asyncio.Event()

        result = manager.request_publish(event)

        self.assertEqual(result['status'], 'unavailable')
        self.assertFalse(event.is_set())

    async def test_connect_reports_socket_error_without_traceback_module(self):
        module, _ = load_mqtt_module()

        class FailingClient:
            async def connect(self):
                raise OSError(104, 'ECONNRESET')

        manager = module.MqttManager('ssid', 'password')
        manager.client = FailingClient()
        self.assertFalse(await manager.connect())
        self.assertFalse(manager.is_connected())


class MqttTaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_mqtt_command_reaches_led_submit(self):
        callbacks = []

        class Manager:
            async def wait_connected(self):
                return True

            async def subscribe(self, topic, qos=0, callback=None):
                callbacks.append(callback)
                return True

        class Led:
            def __init__(self):
                self.receipts = []

            def submit(self, kind, source, value):
                self.receipts.append((kind, source, value))
                return {'status': 'accepted', 'id': 1}

        async def sleep(_):
            raise StopTask()

        task = load_task(
            'mqtt_subscribe_task',
            uasyncio=types.SimpleNamespace(
                sleep=sleep, sleep_ms=asyncio.sleep),
        )
        led = Led()
        with self.assertRaises(StopTask):
            await task(Manager(), led)

        callbacks[0](b'cmd', b'led:4', False)
        self.assertEqual(led.receipts, [('set_color', 'mqtt', 4)])

    async def test_mqtt_subscribe_does_not_claim_connection_after_timeout(self):
        subscribed = []

        class Manager:
            async def wait_connected(self):
                return False

            async def subscribe(self, *args, **kwargs):
                subscribed.append(True)
                return True

        async def sleep(_):
            raise AssertionError('sleep must not run after failed connection')

        task = load_task(
            'mqtt_subscribe_task',
            uasyncio=types.SimpleNamespace(
                sleep=sleep, sleep_ms=asyncio.sleep),
        )
        await task(Manager(), types.SimpleNamespace())
        self.assertEqual(subscribed, [])


class MqttWebTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_api_returns_accepted_and_status_result_separately(self):
        sys.path.insert(0, str(ROOT / 'lib'))
        try:
            with patch.dict(sys.modules, {
                'network': types.ModuleType('network'),
                'uasyncio': asyncio,
            }):
                spec = importlib.util.spec_from_file_location(
                    'web_mqtt_test', ROOT / 'web_server.py')
                web = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(web)

            class Manager:
                def request_publish(self, event):
                    event.set()
                    return {'status': 'accepted', 'request_id': 7, 'error': None}

                def publish_status(self):
                    return {'status': 'published', 'request_id': 7, 'error': None}

            web.mqtt_manager = Manager()
            web.publish_event = asyncio.Event()

            accepted = await web.api_publish(None)
            status = await web.api_publish_status(None)
            self.assertEqual(accepted.status_code, 202)
            self.assertEqual(json.loads(accepted.body)['status'], 'accepted')
            self.assertEqual(json.loads(status.body)['status'], 'published')
        finally:
            sys.path.remove(str(ROOT / 'lib'))

    async def test_publish_api_reports_unavailable_as_json(self):
        sys.path.insert(0, str(ROOT / 'lib'))
        try:
            with patch.dict(sys.modules, {
                'network': types.ModuleType('network'),
                'uasyncio': asyncio,
            }):
                spec = importlib.util.spec_from_file_location(
                    'web_mqtt_unavailable_test', ROOT / 'web_server.py')
                web = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(web)

            web.mqtt_manager = None
            web.publish_event = None
            response = await web.api_publish(None)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                json.loads(response.body)['error'], 'mqtt_not_initialized')
        finally:
            sys.path.remove(str(ROOT / 'lib'))


if __name__ == '__main__':
    unittest.main()
