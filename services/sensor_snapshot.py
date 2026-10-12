"""Last-good sensor values with validity, age and error metadata."""
import time


class SensorSnapshot:
    def __init__(self, clock=None):
        self._clock = clock or time
        self._data = {
            'temperature': self._empty_field(),
            'humidity': self._empty_field(),
            'light': self._empty_field(),
            'sample_seq': 0,
            'status': 'unavailable',
        }

    @staticmethod
    def _empty_field():
        return {
            'value': None,
            'valid': False,
            'quality': 'unavailable',
            'age_ms': None,
            'error': None,
            'updated_at_ms': None,
        }

    def update_dht(self, result, error=None):
        if result is None:
            self._mark_error(('temperature', 'humidity'), error or 'dht_measure_failed')
            return
        try:
            temperature, humidity = result
        except (TypeError, ValueError):
            self._mark_error(('temperature', 'humidity'), 'invalid_dht_result')
            return
        self._update_field('temperature', temperature, error)
        self._update_field('humidity', humidity, error)
        self._data['sample_seq'] += 1
        self._refresh_status()

    def update_light(self, value, error=None):
        self._update_field('light', value, error)
        self._data['sample_seq'] += 1
        self._refresh_status()

    def _update_field(self, name, value, error):
        field = self._data[name]
        now = self._now()
        if error is None and value is not None:
            field.update(value=value, valid=True, quality='good',
                         error=None, updated_at_ms=now)
        else:
            field.update(valid=False, quality='error',
                         error=error or 'sensor_read_failed')

    def _mark_error(self, names, error):
        for name in names:
            field = self._data[name]
            field.update(valid=False, quality='error',
                         error=error or 'sensor_read_failed')
        self._refresh_status()

    def _refresh_status(self):
        fields = (self._data['temperature'], self._data['humidity'], self._data['light'])
        if all(field['valid'] for field in fields):
            self._data['status'] = 'ready'
        elif any(field['valid'] for field in fields):
            self._data['status'] = 'partial'
        else:
            self._data['status'] = 'error'

    def _now(self):
        ticks_ms = getattr(self._clock, 'ticks_ms', None)
        return ticks_ms() if callable(ticks_ms) else int(self._clock.time() * 1000)

    def snapshot(self):
        now = self._now()
        result = {
            'temperature': self._field_snapshot(self._data['temperature'], now),
            'humidity': self._field_snapshot(self._data['humidity'], now),
            'light': self._field_snapshot(self._data['light'], now),
            'sample_seq': self._data['sample_seq'],
            'status': self._data['status'],
        }
        return result

    def _field_snapshot(self, field, now):
        result = dict(field)
        updated_at = result['updated_at_ms']
        if updated_at is not None:
            ticks_diff = getattr(self._clock, 'ticks_diff', None)
            age = ticks_diff(now, updated_at) if callable(ticks_diff) else now - updated_at
            result['age_ms'] = max(0, age)
        return result

    def value(self, name):
        return self.snapshot()[name]['value']
