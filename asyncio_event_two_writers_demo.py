"""示範兩個寫入者共用一份 state 與 asyncio.Event 時的覆蓋情況。"""

import asyncio


state = {"writer": None, "value": None}
event = asyncio.Event()


async def producer(name, value, delay):
    """延遲後寫入同一份共享狀態，並送出通知。"""
    await asyncio.sleep(delay)
    state["writer"] = name
    state["value"] = value
    event.set()
    print(
        "[{}] 寫入 {}，event.is_set() = {}".format(
            name, value, event.is_set()
        )
    )


async def consumer():
    """模擬忙碌後才開始處理通知的消費者。"""
    print("[消費者] 兩個寫入者完成後才開始等待")
    await event.wait()
    event.clear()
    print(
        "[消費者] 只讀到最後狀態：writer={}, value={}".format(
            state["writer"], state["value"]
        )
    )


async def main():
    await asyncio.gather(
        producer("寫入者 A", 100, 0.2),
        producer("寫入者 B", 200, 0.4),
    )
    await consumer()
    print("[結果] A 的 100 已被 B 的 200 覆蓋；Event 不會記錄 set() 次數")


if __name__ == "__main__":
    asyncio.run(main())
