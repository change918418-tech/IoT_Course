"""HLK-LD2410B UART diagnostic for this project's ESP32-S3 wiring.

Copy this file and ``ld2410b_micropython.py`` to the same directory on the
ESP32. Stop the project app and run this file directly; do not overwrite the
project's ``main.py``.
"""

import time

from ld2410b_micropython import LD2410B


# These pins are unused by the current private config.py and config.example.py.
UART_ID = 1
ESP32_TX_PIN = 14  # ESP32 GPIO14 -> LD2410B UART_Rx
ESP32_RX_PIN = 2   # ESP32 GPIO2  <- LD2410B UART_Tx
DEFAULT_BAUDRATE = 256000
PROBE_BAUDRATES = (
    DEFAULT_BAUDRATE,
    115200,
    230400,
    460800,
    57600,
    38400,
    19200,
    9600,
)
PROBE_TIME_MS = 800
READ_TIMEOUT_MS = 2000


def print_wiring():
    print("=== HLK-LD2410B UART diagnostic ===")
    print("LD2410B VCC     -> ESP32 5V/VBUS (not 3.3V)")
    print("LD2410B GND     -> ESP32 GND")
    print("LD2410B UART_Tx -> ESP32 GPIO{} (RX)".format(ESP32_RX_PIN))
    print("LD2410B UART_Rx -> ESP32 GPIO{} (TX, optional for read-only test)".format(
        ESP32_TX_PIN
    ))
    print("UART{}: 8N1; probing supported baud rates.".format(UART_ID))


def _collect_uart_bytes(uart, duration_ms):
    deadline = time.ticks_add(time.ticks_ms(), duration_ms)
    data = bytearray()
    while time.ticks_diff(deadline, time.ticks_ms()) >= 0:
        chunk = uart.read()
        if chunk:
            data.extend(chunk)
        time.sleep_ms(10)
    return data


def _contains_data_frame(data):
    search_from = 0
    while True:
        start = data.find(LD2410B.DATA_HEAD, search_from)
        if start < 0 or len(data) < start + 6:
            return False
        payload_length = data[start + 4] | (data[start + 5] << 8)
        payload_start = start + 6
        payload_end = payload_start + payload_length
        frame_end = payload_end + 4
        if (
            payload_length >= 13
            and frame_end <= len(data)
            and data[payload_start + 1] == 0xaa
            and data[payload_end - 2:payload_end] == b"\x55\x00"
            and data[payload_end:frame_end] == LD2410B.DATA_TAIL
        ):
            return True
        search_from = start + 1


def _hex_preview(data, limit=32):
    preview = "".join("{:02x}".format(value) for value in data[:limit])
    if len(data) > limit:
        preview += "..."
    return preview


def probe_radar():
    total_bytes = 0
    strongest = None

    for baudrate in PROBE_BAUDRATES:
        radar = LD2410B(
            uart_id=UART_ID,
            tx=ESP32_TX_PIN,
            rx=ESP32_RX_PIN,
            baudrate=baudrate,
        )
        raw = _collect_uart_bytes(radar.uart, PROBE_TIME_MS)
        count = len(raw)
        total_bytes += count
        valid_frame = _contains_data_frame(raw)
        print(
            "[probe] {} baud: {} byte(s), frame={}".format(
                baudrate, count, "yes" if valid_frame else "no"
            )
        )

        if valid_frame:
            return radar, baudrate
        if count and (strongest is None or count > strongest[0]):
            strongest = (count, baudrate, bytes(raw))
        radar.uart.deinit()

    if total_bytes == 0:
        raise OSError(
            "GPIO{} RX received 0 bytes at every supported baud rate".format(
                ESP32_RX_PIN
            )
        )

    count, baudrate, raw = strongest
    raise OSError(
        "UART bytes were present but no LD2410B frame was found; "
        "strongest={} baud/{} bytes, raw={}".format(
            baudrate, count, _hex_preview(raw)
        )
    )


def print_sample(sequence, data):
    print(
        "#{:05d} state={} move={}cm/{} still={}cm/{} detect={}cm".format(
            sequence,
            data["target_state"],
            data["moving_distance_cm"],
            data["moving_energy"],
            data["stationary_distance_cm"],
            data["stationary_energy"],
            data["detection_distance_cm"],
        )
    )
    if "light_level" in data:
        print(
            "         engineering: light={} out={}".format(
                data["light_level"], data["out_level"]
            )
        )


def print_no_frame_help():
    print("This is a raw UART receive failure, not a parser timeout.")
    print("Check stable 5V and common GND first.")
    print("Check the module-side UART_Tx is connected to ESP32 GPIO{}.".format(
        ESP32_RX_PIN
    ))
    print("For receive-only diagnosis, GPIO14 -> UART_Rx may be disconnected.")
    print("Never connect 5V to an ESP32 GPIO.")


def main():
    print_wiring()
    print("Do not move yet; first checking the continuous radar data stream.")
    try:
        radar, baudrate = probe_radar()
    except OSError as exc:
        print("[error]", exc)
        print_no_frame_help()
        return
    except KeyboardInterrupt:
        print("LD2410B test stopped.")
        return

    print("[ok] Valid LD2410B frame detected at {} baud.".format(baudrate))
    print("Move in front of the radar; press Ctrl+C to stop.")

    sequence = 0
    while True:
        try:
            sample = radar.read(timeout_ms=READ_TIMEOUT_MS)
            sequence += 1
            print_sample(sequence, sample)
        except OSError as exc:
            print("[error] Radar data stream stopped:", exc)
            print_no_frame_help()
            return
        except KeyboardInterrupt:
            print("LD2410B test stopped.")
            return


if __name__ == "__main__":
    main()
