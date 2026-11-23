"""Minimal MicroPython driver for the HLK-LD2410B radar module.

The driver keeps the wire protocol small and explicit:
- normal/engineering data frames are parsed from UART;
- configuration commands use the documented enter-command-exit sequence;
- no third-party package is required.
"""

import time

try:
    from machine import UART
except ImportError:  # Allows syntax checks on a desktop; ESP32 supplies machine.UART.
    UART = None


class LD2410B:
    DATA_HEAD = b"\xf4\xf3\xf2\xf1"
    DATA_TAIL = b"\xf8\xf7\xf6\xf5"
    CMD_HEAD = b"\xfd\xfc\xfb\xfa"
    CMD_TAIL = b"\x04\x03\x02\x01"
    TARGET_STATES = {
        0x00: "none",
        0x01: "moving",
        0x02: "stationary",
        0x03: "moving_and_stationary",
        0x04: "noise_checking",
        0x05: "noise_check_ok",
        0x06: "noise_check_failed",
    }

    def __init__(self, uart_id=1, tx=None, rx=None, uart=None, baudrate=256000):
        if uart is not None:
            self.uart = uart
        else:
            if UART is None:
                raise RuntimeError("machine.UART is unavailable")
            kwargs = {
                "baudrate": baudrate,
                "bits": 8,
                "parity": None,
                "stop": 1,
            }
            if tx is not None:
                kwargs["tx"] = tx
            if rx is not None:
                kwargs["rx"] = rx
            self.uart = UART(uart_id, **kwargs)
        self._buffer = bytearray()

    @staticmethod
    def _le16(value):
        return bytes((value & 0xff, (value >> 8) & 0xff))

    @staticmethod
    def _le32(value):
        return bytes((value & 0xff, (value >> 8) & 0xff,
                      (value >> 16) & 0xff, (value >> 24) & 0xff))

    @staticmethod
    def _u16(data, offset):
        return data[offset] | (data[offset + 1] << 8)


    def _append_uart_data(self):
        chunk = self.uart.read()
        if chunk:
            self._buffer.extend(chunk)

    def _discard_buffer_prefix(self, count):
        """Discard bytes without bytearray item deletion, unsupported on MicroPython."""
        if count <= 0:
            return
        self._buffer = self._buffer[count:]

    def _extract_frame(self):
        while len(self._buffer) >= 6:
            data_start = self._buffer.find(self.DATA_HEAD)
            command_start = self._buffer.find(self.CMD_HEAD)
            starts = [item for item in (data_start, command_start) if item >= 0]
            if not starts:
                # Keep only the bytes that may be the beginning of a split header.
                self._discard_buffer_prefix(len(self._buffer) - 3)
                return None

            start = min(starts)
            is_command = command_start >= 0 and command_start == start
            tail = self.CMD_TAIL if is_command else self.DATA_TAIL
            if start:
                self._discard_buffer_prefix(start)
            if len(self._buffer) < 6:
                return None

            payload_length = self._u16(self._buffer, 4)
            if payload_length < 4 or payload_length > 128:
                self._discard_buffer_prefix(1)
                continue

            frame_length = 10 + payload_length
            if len(self._buffer) < frame_length:
                return None
            if bytes(self._buffer[frame_length - 4:frame_length]) != tail:
                self._discard_buffer_prefix(1)
                continue

            frame = bytes(self._buffer[:frame_length])
            self._discard_buffer_prefix(frame_length)
            return frame
        return None

    def _read_frame(self, timeout_ms):
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) >= 0:
            self._append_uart_data()
            frame = self._extract_frame()
            if frame is not None:
                return frame
            time.sleep_ms(1)
        raise OSError("LD2410B frame timeout")

    @classmethod
    def _parse_data_frame(cls, frame):
        payload = frame[6:-4]
        if len(payload) < 13 or payload[1] != 0xaa or payload[-2:] != b"\x55\x00":
            return None

        result = {
            "frame_type": payload[0],
            "target_state_code": payload[2],
            "target_state": cls.TARGET_STATES.get(payload[2], "unknown"),
            "moving_distance_cm": cls._u16(payload, 3),
            "moving_energy": payload[5],
            "stationary_distance_cm": cls._u16(payload, 6),
            "stationary_energy": payload[8],
            "detection_distance_cm": cls._u16(payload, 9),
        }

        # Engineering mode appends gate counts, 9+9 gate energies, light and OUT.
        if payload[0] == 0x01 and len(payload) >= 35:
            result["max_moving_gate"] = payload[11]
            result["max_stationary_gate"] = payload[12]
            result["moving_gate_energy"] = list(payload[13:22])
            result["stationary_gate_energy"] = list(payload[22:31])
            result["light_level"] = payload[31]
            result["out_level"] = payload[32]
        return result

    def read(self, timeout_ms=1000):
        """Read and parse the next radar data frame."""
        while True:
            frame = self._read_frame(timeout_ms)
            parsed = self._parse_data_frame(frame)
            if parsed is not None:
                return parsed

    @classmethod
    def _command_frame(cls, command, value=b""):
        body = cls._le16(command) + value
        return cls.CMD_HEAD + cls._le16(len(body)) + body + cls.CMD_TAIL

    @staticmethod
    def _ack_command(command):
        return bytes((command & 0xff, ((command >> 8) + 1) & 0xff))

    def send_command(self, command, value=b"", timeout_ms=1000):
        """Send one configuration command and return ACK data after status."""
        self.uart.write(self._command_frame(command, value))
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        expected = self._ack_command(command)

        while time.ticks_diff(deadline, time.ticks_ms()) >= 0:
            remaining = time.ticks_diff(deadline, time.ticks_ms())
            try:
                frame = self._read_frame(max(1, remaining))
            except OSError:
                break
            payload = frame[6:-4]
            if len(payload) < 4 or payload[:2] != expected:
                continue
            status = self._u16(payload, 2)
            if status != 0:
                raise OSError("LD2410B command failed: 0x%04x" % status)
            return payload[4:]
        raise OSError("LD2410B ACK timeout: 0x%04x" % command)

    def enter_config(self):
        return self.send_command(0x00ff, self._le16(0x0001))

    def exit_config(self):
        return self.send_command(0x00fe)

    def read_config(self):
        """Read current parameters; the method handles enter/exit automatically."""
        self.enter_config()
        try:
            return self.send_command(0x0061)
        finally:
            self.exit_config()

    def set_max_distance_and_timeout(self, moving_gate, stationary_gate,
                                     no_target_seconds):
        """Set max gates and no-target duration; values persist after reboot."""
        value = (
            self._le16(0x0000) + self._le32(moving_gate) +
            self._le16(0x0001) + self._le32(stationary_gate) +
            self._le16(0x0002) + self._le32(no_target_seconds)
        )
        self.enter_config()
        try:
            return self.send_command(0x0060, value)
        finally:
            self.exit_config()
