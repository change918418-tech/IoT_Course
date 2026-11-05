"""實驗 2：同時監聽三個按鈕，觀察非同步去彈跳與釋放等待。"""

import uasyncio as asyncio

import config
from hardware.button import Button


async def monitor_button(button_id, button):
    while True:
        await button.wait_press()
        print("[按鈕 {}] 穩定按下，GPIO={}".format(
            button_id, button.pin_num))
        await button.wait_release()
        print("[按鈕 {}] 已釋放；其他 task 在等待期間仍可執行".format(
            button_id))


async def heartbeat():
    count = 0
    while True:
        print("[heartbeat] {}：event loop 仍在運作".format(count))
        count += 1
        await asyncio.sleep(1)


async def main():
    buttons = (
        (1, Button(config.BUTTON1_PIN)),
        (2, Button(config.BUTTON2_PIN)),
        (3, Button(config.BUTTON3_PIN)),
    )
    print("實驗 2：按下任一按鈕；按下為低電位")
    await asyncio.gather(
        monitor_button(buttons[0][0], buttons[0][1]),
        monitor_button(buttons[1][0], buttons[1][1]),
        monitor_button(buttons[2][0], buttons[2][1]),
        heartbeat(),
    )


if __name__ == "__main__":
    asyncio.run(main())
