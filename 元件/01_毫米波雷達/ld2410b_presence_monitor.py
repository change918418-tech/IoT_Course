"""Print LD2410B distance, presence, and moving-target energy.

Upload this file and ld2410b_micropython.py to the same ESP32 directory.
The UART pins follow the root test_ld2410b_uart.py wiring used by this project.
"""

from ld2410b_micropython import LD2410B


UART_ID = 1
ESP32_TX_PIN = 2   # ESP32 GPIO2  -> LD2410B UART_Rx
ESP32_RX_PIN = 14  # ESP32 GPIO14 <- LD2410B UART_Tx
BAUDRATE = 256000
READ_TIMEOUT_MS = 2000

_PRESENT_CODES = (0x01, 0x02, 0x03)
_NO_TARGET_CODE = 0x00


def presence_text(target_state_code):
    """Return a human-readable presence result for an LD2410B state code."""
    if target_state_code in _PRESENT_CODES:
        return "有人"
    if target_state_code == _NO_TARGET_CODE:
        return "無人"
    return "未知"


def print_sample(data):
    """Print the three values required by this standalone monitor."""
    print(
        "距離: {} cm | 狀態: {} | 移動能量: {}".format(
            data["detection_distance_cm"],
            presence_text(data["target_state_code"]),
            data["moving_energy"],
        )
    )


def main():
    print("=== HLK-LD2410B 距離／有人／移動能量 ===")
    print(
        "UART{}: TX=GPIO{}, RX=GPIO{}, baudrate={}".format(
            UART_ID, ESP32_TX_PIN, ESP32_RX_PIN, BAUDRATE
        )
    )

    radar = LD2410B(
        uart_id=UART_ID,
        tx=ESP32_TX_PIN,
        rx=ESP32_RX_PIN,
        baudrate=BAUDRATE,
    )

    try:
        while True:
            try:
                print_sample(radar.read(timeout_ms=READ_TIMEOUT_MS))
            except OSError as exc:
                print("雷達讀取失敗:", exc)
    except KeyboardInterrupt:
        print("雷達監看已停止")
    finally:
        deinit = getattr(radar.uart, "deinit", None)
        if deinit is not None:
            deinit()


if __name__ == "__main__":
    main()
