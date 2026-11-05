"""用一個生產者與一個消費者示範 asyncio.Event 的通知流程。"""

import asyncio


state = {"value": None}
event = asyncio.Event()


def read_value():
    """模擬從感測器取得資料。"""
    return 42


def use(value):
    """模擬消費者使用資料。"""
    print("[消費者] 使用資料：{}".format(value))


async def producer():
    print("[生產者] 等待 1 秒，模擬讀取感測器...")
    await asyncio.sleep(1)

    state["value"] = read_value()
    print("[生產者] 資料已寫入 state：{}".format(state["value"]))

    event.set()
    print("[生產者] event.set()：通知消費者")


async def consumer():
    print("[消費者] await event.wait()：等待資料")
    await event.wait()
    print("[消費者] 收到通知")

    event.clear()
    print("[消費者] event.clear()：將事件恢復為等待狀態")
    use(state["value"])


async def main():
    await asyncio.gather(consumer(), producer())


if __name__ == "__main__":
    asyncio.run(main())
