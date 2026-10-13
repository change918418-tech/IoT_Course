"""Single LED owner: bounded admission, arbitration and timed rendering."""
import time
import uasyncio
import config
from communication.wifi import get_current_time


class LedController:
    """唯一 LED 硬體寫入者；所有 producer 只提交命令。"""

    VALID_KINDS = ('cycle', 'set_color', 'set_mode', 'low_light_alert')
    VALID_MODES = ('AUTO', 'MANUAL')

    def __init__(self, hardware, clock=None, mode=None):
        self._hardware = hardware
        self._clock = clock or time
        self._queue = []
        self._results = []
        self._next_id = 1
        self._reserved = False
        self._stopping = False
        self._stopped = uasyncio.Event()
        self._desired_color = 7
        self._enabled = True
        configured_mode = mode or getattr(config, 'LED_CONTROL_MODE', 'AUTO')
        self._mode = configured_mode if configured_mode in self.VALID_MODES else 'AUTO'
        self._applied_output = None
        self._effect = None
        self._inflight = None
        self._error = None
        self._alert_count = 0
        self._alert_log = []
        self.frame_ms = 20
        self.capacity = 8
        self.result_capacity = 16
        self.max_commands_per_frame = 4

    @property
    def busy(self):
        return self._reserved

    def submit(self, kind, source, value=None):
        """Compatibility helper for owner tests; production uses CommandService."""
        request_id = self._allocate_id()
        return self.submit_command({
            'request_id': request_id,
            'kind': kind,
            'source': source,
            'value': value,
        })

    def submit_command(self, command):
        """Synchronously admit a normalized command; never touches GPIO."""
        request_id = command.get('request_id')
        if request_id is None:
            request_id = self._allocate_id()
        elif request_id >= self._next_id:
            self._next_id = request_id + 1

        kind = command.get('kind')
        source = command.get('source')
        value = command.get('value')
        receipt = {
            'id': request_id,
            'request_id': request_id,
            'kind': kind,
            'source': source,
            'value': value,
            'status': 'accepted',
            'reason': None,
        }
        self._remember(receipt)

        reason = self._validation_reason(kind, source, value)
        if reason is None and self._stopping:
            reason = 'stopped'
        elif reason is None and self.busy:
            reason = 'busy'
        elif reason is None and kind != 'low_light_alert' and len(self._queue) >= self.capacity:
            reason = 'queue_full'
        if reason is not None:
            receipt.update(status='rejected', reason=reason)
            return dict(receipt)

        if kind == 'low_light_alert':
            self._reserved = True
            self._reject_pending('alert_started')
        self._queue.append((kind, value, receipt))
        return dict(receipt)

    def _allocate_id(self):
        request_id = self._next_id
        self._next_id += 1
        return request_id

    def _validation_reason(self, kind, source, value):
        if not isinstance(source, str) or not source:
            return 'invalid_source'
        if kind not in self.VALID_KINDS:
            return 'invalid_command'
        if kind == 'set_color' and (not isinstance(value, int) or not 0 <= value <= 7):
            return 'invalid_color'
        if kind == 'set_mode' and value not in self.VALID_MODES:
            return 'invalid_mode'
        if kind == 'low_light_alert' and self._mode != 'AUTO':
            return 'manual_mode'
        return None

    def _remember(self, receipt):
        self._results.append(receipt)
        if len(self._results) > self.result_capacity:
            self._results.pop(0)

    def _reject_pending(self, reason):
        for _, _, receipt in self._queue:
            if receipt['status'] == 'accepted':
                receipt.update(status='rejected', reason=reason)
        self._queue.clear()

    def result(self, request_id):
        for receipt in self._results:
            if receipt['id'] == request_id or receipt['request_id'] == request_id:
                return dict(receipt)
        return None

    def snapshot(self):
        return {
            'available': not self._stopping,
            'mode': self._mode,
            'desired_color': self._desired_color,
            'enabled': self._enabled,
            'applied_output': self._applied_output,
            'color_index': self._desired_color,
            'is_on': self._enabled,
            'alert_active': self.busy,
            'queue_depth': len(self._queue),
            'queue_capacity': self.capacity,
            'error': self._error,
            'alert_flash_count': self._alert_count,
            'alert_flash_total': getattr(config, 'LIGHT_ALERT_BLINK_COUNT', 5),
            'alert_flash_log': [dict(item) for item in self._alert_log],
            'last_command': dict(self._results[-1]) if self._results else None,
        }

    def request_stop(self):
        self._stopping = True
        self._reject_pending('stopped')

    async def wait_stopped(self):
        await self._stopped.wait()

    def _record_alert_event(self):
        try:
            date_str, _, time_str = get_current_time()
            timestamp = '{} {}'.format(date_str, time_str)
        except Exception:
            timestamp = '時間未知'
        self._alert_count += 1
        self._alert_log.append({'sequence': self._alert_count, 'time': timestamp})
        if len(self._alert_log) > 5:
            self._alert_log.pop(0)

    def _apply(self, kind, value, receipt, now):
        if kind == 'low_light_alert':
            self._effect = {
                'phase_on': True,
                'completed': 0,
                'started': now,
                'count': getattr(config, 'LIGHT_ALERT_BLINK_COUNT', 5),
                'on_ms': getattr(config, 'LIGHT_ALERT_ON_MS', 300),
                'off_ms': getattr(config, 'LIGHT_ALERT_OFF_MS', 300),
                'saved': (self._desired_color, self._enabled),
                'receipt': receipt,
            }
        elif kind == 'set_mode':
            self._mode = value
            receipt['status'] = 'executing'
        elif kind == 'cycle':
            self._desired_color = (self._desired_color + 1) % 8
            self._enabled = self._desired_color != 0
            receipt['status'] = 'executing'
        elif kind == 'set_color':
            self._desired_color = value
            self._enabled = value != 0
            receipt['status'] = 'executing'

    def _step(self, now):
        for _ in range(self.max_commands_per_frame):
            if not self._queue:
                break
            kind, value, receipt = self._queue.pop(0)
            self._apply(kind, value, receipt, now)
            if kind != 'low_light_alert' and receipt['status'] == 'executing':
                self._inflight = receipt
                self._write_output(self._desired_color if self._enabled else 0)
                receipt['status'] = 'executed'
                self._inflight = None

        effect = self._effect
        finished = None
        if effect is not None:
            duration = effect['on_ms'] if effect['phase_on'] else effect['off_ms']
            if self._clock.ticks_diff(now, effect['started']) >= duration:
                effect['started'] = now
                if effect['phase_on']:
                    effect['phase_on'] = False
                else:
                    effect['completed'] += 1
                    if effect['completed'] >= effect['count']:
                        self._desired_color, self._enabled = effect['saved']
                        self._record_alert_event()
                        finished = effect['receipt']
                        self._effect = None
                    else:
                        effect['phase_on'] = True

        output = ((4 if self._effect['phase_on'] else 0) if self._effect
                  else (self._desired_color if self._enabled else 0))
        self._write_output(output)
        if finished is not None:
            finished['status'] = 'executed'
            self._reserved = False

    def _write_output(self, output):
        self._hardware.write(output)
        self._applied_output = output

    async def run(self):
        print('[LED Controller] 已啟動，命令上限8，每輪最多4筆，frame=20 ms')
        try:
            while not self._stopping:
                self._step(self._clock.ticks_ms())
                await uasyncio.sleep_ms(self.frame_ms)
        except Exception as e:
            self._error = str(e)
            if self._inflight is not None:
                self._inflight.update(status='failed', reason=self._error)
            for _, _, receipt in self._queue:
                receipt.update(status='failed', reason=self._error)
            if self._effect is not None:
                self._effect['receipt'].update(status='failed', reason=self._error)
            for receipt in self._results:
                if receipt['status'] in ('accepted', 'executing'):
                    receipt.update(status='failed', reason=self._error)
            raise
        finally:
            self._stopping = True
            for kind, _, receipt in self._queue:
                if kind == 'low_light_alert' and receipt['status'] == 'accepted':
                    receipt.update(status='cancelled', reason='stopped')
            self._reject_pending('stopped')
            if self._effect is not None:
                receipt = self._effect['receipt']
                if receipt['status'] in ('accepted', 'executing'):
                    receipt.update(status='cancelled', reason='stopped')
            self._effect = None
            self._reserved = False
            try:
                self._write_output(0)
            finally:
                self._stopped.set()
