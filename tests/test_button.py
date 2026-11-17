"""Button release/timeout boundary tests with fake GPIO."""
import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class FakePin:
    IN = 0
    PULL_UP = 1
    instances = []

    def __init__(self, pin_num, mode, pull):
        self.pin_num = pin_num
        self.level = 0
        self.__class__.instances.append(self)

    def value(self):
        return self.level


def load_button(sleep_ms):
    FakePin.instances.clear()
    machine = types.ModuleType('machine')
    machine.Pin = FakePin
    fake_asyncio = types.SimpleNamespace(sleep_ms=sleep_ms)
    with patch.dict(sys.modules, {
        'machine': machine,
        'uasyncio': fake_asyncio,
    }):
        spec = importlib.util.spec_from_file_location(
            'button_boundary_test', ROOT / 'hardware' / 'button.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class ButtonBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_release_observed_at_deadline_wins_over_timeout(self):
        elapsed = 0

        async def sleep_ms(delay):
            nonlocal elapsed
            elapsed += delay
            if elapsed == 800:
                FakePin.instances[0].level = 1

        module = load_button(sleep_ms)
        button = module.Button(17)
        button.is_pressed = True

        released = await button.wait_release(timeout_ms=800)

        self.assertTrue(released)
        self.assertEqual(elapsed, 800)
        self.assertFalse(button.is_pressed)

    async def test_held_button_returns_timeout_without_clearing_pressed_state(self):
        elapsed = 0

        async def sleep_ms(delay):
            nonlocal elapsed
            elapsed += delay

        module = load_button(sleep_ms)
        button = module.Button(17)
        button.is_pressed = True

        released = await button.wait_release(timeout_ms=800)

        self.assertFalse(released)
        self.assertEqual(elapsed, 800)
        self.assertTrue(button.is_pressed)

    async def test_cancellation_clears_state_if_button_was_released(self):
        waiting = asyncio.Event()

        async def sleep_ms(_):
            waiting.set()
            await asyncio.Event().wait()

        module = load_button(sleep_ms)
        button = module.Button(17)
        button.is_pressed = True
        running = asyncio.create_task(button.wait_release(timeout_ms=800))
        await waiting.wait()
        button.pin.level = 1
        running.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await running
        self.assertFalse(button.is_pressed)


if __name__ == '__main__':
    unittest.main()
