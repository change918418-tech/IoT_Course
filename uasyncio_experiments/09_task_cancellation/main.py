"""實驗 9：比較停止事件與 task.cancel()，並確認 finally 清理。"""

try:
    import uasyncio as asyncio
except ImportError:  # 允許桌面 CPython smoke
    import asyncio


async def sleep_ms(milliseconds):
    if hasattr(asyncio, "sleep_ms"):
        await asyncio.sleep_ms(milliseconds)
    else:
        await asyncio.sleep(milliseconds / 1000)


class FakeOutput:
    def __init__(self, name):
        self.name = name
        self.active = False

    def on(self):
        self.active = True

    def off(self):
        self.active = False
        print("- {} 已清理為關閉".format(self.name))


async def worker(name, stop_event, stopped_event, output):
    output.on()
    count = 0
    try:
        while not stop_event.is_set():
            print("- {} working {}".format(name, count))
            count += 1
            await sleep_ms(100)
    finally:
        output.off()
        stopped_event.set()


async def graceful_stop_demo():
    print("實驗 9A：stop request + stopped confirmation")
    stop_event = asyncio.Event()
    stopped_event = asyncio.Event()
    output = FakeOutput("graceful output")
    task = asyncio.create_task(worker(
        "graceful worker", stop_event, stopped_event, output))
    await sleep_ms(250)
    stop_event.set()
    await stopped_event.wait()
    await task
    print("- confirmation 收到，active={}".format(output.active))


async def cancellation_demo():
    print("\n實驗 9B：task.cancel()")
    stop_event = asyncio.Event()
    stopped_event = asyncio.Event()
    output = FakeOutput("cancelled output")
    task = asyncio.create_task(worker(
        "cancelled worker", stop_event, stopped_event, output))
    await sleep_ms(250)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("- 已收到 CancelledError")
    await stopped_event.wait()
    print("- cancellation cleanup 完成，active={}".format(output.active))


async def main():
    await graceful_stop_demo()
    await cancellation_demo()


if __name__ == "__main__":
    asyncio.run(main())
