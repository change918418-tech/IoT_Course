"""Desktop regression tests for the LD2410B stream parser."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DRIVER_PATH = ROOT / "元件" / "01_毫米波雷達" / "ld2410b_micropython.py"
SPEC = importlib.util.spec_from_file_location("ld2410b_driver", DRIVER_PATH)
DRIVER_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER_MODULE)
LD2410B = DRIVER_MODULE.LD2410B


class FakeUart:
    def read(self):
        return None


class NoDeleteBytearray(bytearray):
    """Model MicroPython bytearray, which rejects item deletion."""

    def __delitem__(self, key):
        raise TypeError("bytearray item deletion is unavailable")


class Ld2410bDriverTests(unittest.TestCase):
    def test_extract_frame_does_not_require_bytearray_item_deletion(self):
        frame = bytes.fromhex(
            "f4f3f2f10d0002aa0251000000003b00005500f8f7f6f5"
        )
        radar = LD2410B(uart=FakeUart())
        radar._buffer = NoDeleteBytearray(b"\x99\x88" + frame + frame)

        extracted = radar._extract_frame()

        self.assertEqual(extracted, frame)
        self.assertEqual(bytes(radar._buffer), frame)
        self.assertEqual(
            radar._parse_data_frame(extracted),
            {
                "frame_type": 2,
                "target_state_code": 2,
                "target_state": "stationary",
                "moving_distance_cm": 81,
                "moving_energy": 0,
                "stationary_distance_cm": 0,
                "stationary_energy": 59,
                "detection_distance_cm": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
