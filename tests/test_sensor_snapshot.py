"""SensorSnapshot quality and last-good value tests."""
import unittest
from services.sensor_snapshot import SensorSnapshot


class Clock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now


class SensorSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.snapshot = SensorSnapshot(self.clock)

    def test_success_records_values_quality_and_age(self):
        self.snapshot.update_dht((25, 60))
        self.snapshot.update_light(0)
        self.clock.now = 125
        data = self.snapshot.snapshot()
        self.assertEqual(data['temperature']['value'], 25)
        self.assertTrue(data['temperature']['valid'])
        self.assertEqual(data['temperature']['quality'], 'good')
        self.assertEqual(data['temperature']['age_ms'], 125)
        self.assertEqual(data['light']['value'], 0)
        self.assertEqual(data['status'], 'ready')

    def test_failed_read_retains_last_good_value_and_marks_quality(self):
        self.snapshot.update_dht((25, 60))
        self.clock.now = 200
        self.snapshot.update_dht(None, 'timeout')
        data = self.snapshot.snapshot()
        self.assertEqual(data['temperature']['value'], 25)
        self.assertFalse(data['temperature']['valid'])
        self.assertEqual(data['temperature']['quality'], 'error')
        self.assertEqual(data['temperature']['error'], 'timeout')
        self.assertEqual(data['temperature']['age_ms'], 200)
        self.assertEqual(data['status'], 'error')

    def test_zero_is_valid_not_missing(self):
        self.snapshot.update_dht((0, 0))
        self.snapshot.update_light(0)
        data = self.snapshot.snapshot()
        self.assertEqual(data['temperature']['value'], 0)
        self.assertEqual(data['humidity']['value'], 0)
        self.assertEqual(data['light']['value'], 0)
        self.assertTrue(data['temperature']['valid'])


if __name__ == '__main__':
    unittest.main()
