"""HLK-LD2410B UART smoke test for this project's ESP32-S3 wiring.

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
BAUDRATE = 256000
READ_TIMEOUT_MS = 2000


def print_wiring():
    print("=== HLK-LD2410B UART test ===")
    print("LD2410B VCC     -> ESP32 5V/VBUS (not 3.3V)")
    print("LD2410B GND     -> ESP32 GND")
    print("LD2410B UART_Tx -> ESP32 GPIO{} (RX)".format(ESP32_RX_PIN))
    print("LD2410B UART_Rx -> ESP32 GPIO{} (TX)".format(ESP32_TX_PIN))
    print("UART{}: {} baud, 8N1".format(UART_ID, BAUDRATE))


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


def main():
    print_wiring()
    radar = LD2410B(
        uart_id=UART_ID,
        tx=ESP32_TX_PIN,
        rx=ESP32_RX_PIN,
        baudrate=BAUDRATE,
    )
    print("Move in front of the radar; press Ctrl+C to stop.")

    sequence = 0
    while True:
        try:
            sample = radar.read(timeout_ms=READ_TIMEOUT_MS)
            sequence += 1
            print_sample(sequence, sample)
        except OSError as exc:
            print("[timeout]", exc)
            print("Check 5V/GND, crossed TX/RX, and 256000 baud.")
            time.sleep_ms(500)
        except KeyboardInterrupt:
            print("LD2410B test stopped.")
            return


if __name__ == "__main__":
    main()
