"""實驗 1：觀察兩個 coroutine 在 await 邊界交錯執行。"""

try:
    import uasyncio as asyncio
except ImportError:  # 允許在桌面 CPython 觀察相同概念
    import asyncio


async def sleep_ms(milliseconds):
    if hasattr(asyncio, "sleep_ms"):
        await asyncio.sleep_ms(milliseconds)
    else:
        await asyncio.sleep(milliseconds / 1000)


async def fast_task():
    for index in range(5):
        print("fast", index)
        await sleep_ms(200)


async def slow_task():
    for index in range(3):
        print("slow", index)
        await sleep_ms(500)


async def main():
    print("實驗 1：兩個 coroutine 開始")
    await asyncio.gather(fast_task(), slow_task())
    print("all done")


if __name__ == "__main__":
    asyncio.run(main())
