"""Single LED owner: bounded command admission, arbitration and timed rendering."""
import time
import uasyncio
import config
from communication.wifi import get_current_time


class LedService:
    def __init__(self, hardware, clock=None):
        self._hardware = hardware
        self._clock = clock or time
        self._queue = []
        self._results = []
        self._next_id = 1
        self._reserved = False
        self._stopping = False
        self._stopped = uasyncio.Event()
        self._desired_color = 7
        self._desired_on = True
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
        """Synchronous admission only: no GPIO and no await. Return a receipt."""
        receipt = {'id': self._next_id, 'kind': kind, 'source': source,
                   'status': 'accepted', 'reason': None}
        self._next_id += 1
        self._results.append(receipt)
        if len(self._results) > self.result_capacity:
            self._results.pop(0)
        reason = None
        if kind not in ('cycle', 'set_color', 'low_light_alert'):
            reason = 'invalid_command'
        elif kind == 'set_color' and (not isinstance(value, int) or not 0 <= value <= 7):
            reason = 'invalid_color'
        elif self._stopping:
            reason = 'stopped'
        elif self.busy:
            reason = 'busy'
        elif kind != 'low_light_alert' and len(self._queue) >= self.capacity:
            reason = 'queue_full'
        if reason:
            receipt.update(status='rejected', reason=reason)
        else:
            if kind == 'low_light_alert':
                # Reserve immediately, before owner gets scheduled. No stale cycles
                # may survive and run after the alert. Pending callers see rejection.
                self._reserved = True
                self._reject_pending('alert_started')
            self._queue.append((kind, value, receipt))
        return dict(receipt)

    def _reject_pending(self, reason):
        for _, _, receipt in self._queue:
            if receipt['status'] == 'accepted':
                receipt.update(status='rejected', reason=reason)
        self._queue.clear()

    def result(self, command_id):
        for receipt in self._results:
            if receipt['id'] == command_id:
                return dict(receipt)
        return None

    def snapshot(self):
        return {'available': not self._stopping, 'alert_active': self.busy,
                'color_index': self._desired_color, 'is_on': self._desired_on,
                'queue_depth': len(self._queue), 'error': self._error,
                'alert_flash_count': self._alert_count,
                'alert_flash_total': getattr(config, 'LIGHT_ALERT_BLINK_COUNT', 5),
                'alert_flash_log': [dict(item) for item in self._alert_log],
                'last_command': dict(self._results[-1]) if self._results else None}

    def request_stop(self):
        """Control-plane stop request; only run() writes the shutdown output."""
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
        self._alert_log.append({
            'sequence': self._alert_count,
            'time': timestamp
        })
        if len(self._alert_log) > 5:
            self._alert_log.pop(0)

    def _apply(self, kind, value, receipt, now):
        if kind == 'low_light_alert':
            self._effect = {'phase_on': True, 'completed': 0, 'started': now,
                'count': getattr(config, 'LIGHT_ALERT_BLINK_COUNT', 5),
                'on_ms': getattr(config, 'LIGHT_ALERT_ON_MS', 300),
                'off_ms': getattr(config, 'LIGHT_ALERT_OFF_MS', 300),
                'saved': (self._desired_color, self._desired_on),
                'receipt': receipt}
        elif self.busy:
            receipt.update(status='rejected', reason='busy')
        else:
            self._desired_color = ((self._desired_color + 1) % 8
                                   if kind == 'cycle' else value)
            self._desired_on = self._desired_color != 0
            receipt['status'] = 'executing'

    def _step(self, now):
        """Owner-only frame; tests call it with a virtual clock, never producers."""
        for _ in range(self.max_commands_per_frame):
            if not self._queue:
                break
            kind, value, receipt = self._queue.pop(0)
            self._apply(kind, value, receipt, now)
            if kind != 'low_light_alert' and receipt['status'] == 'executing':
                # Render each accepted cycle, do not merge relative changes.
                self._inflight = receipt
                self._hardware.write(self._desired_color if self._desired_on else 0)
                receipt['status'] = 'executed'
                self._inflight = None
        effect = self._effect
        finished = None
        if effect is not None:
            duration = effect['on_ms'] if effect['phase_on'] else effect['off_ms']
            if self._clock.ticks_diff(now, effect['started']) >= duration:
                # One transition per frame; scheduler delay lengthens a phase
                # rather than skipping visible flashes in a catch-up burst.
                effect['started'] = now
                if effect['phase_on']:
                    effect['phase_on'] = False
                else:
                    effect['completed'] += 1
                    if effect['completed'] >= effect['count']:
                        self._desired_color, self._desired_on = effect['saved']
                        self._record_alert_event()
                        finished = effect['receipt']
                        self._effect = None
                    else:
                        effect['phase_on'] = True
        output = ((4 if self._effect['phase_on'] else 0) if self._effect
                  else (self._desired_color if self._desired_on else 0))
        self._hardware.write(output)
        if finished is not None:
            finished['status'] = 'executed'
            self._reserved = False  # Only after restore write succeeds.

    async def run(self):
        print('[LED Owner] 已啟動，命令上限8，每輪最多4筆，frame=20 ms')
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
                self._hardware.write(0)
            finally:
                self._stopped.set()
