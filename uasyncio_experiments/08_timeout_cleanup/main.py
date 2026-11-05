"""實驗 8：以 timeout 與錯誤注入驗證 finally 的安全清理。"""

try:
    import uasyncio as asyncio
except ImportError:  # 允許桌面 CPython smoke
    import asyncio


async def sleep_ms(milliseconds):
    if hasattr(asyncio, "sleep_ms"):
        await asyncio.sleep_ms(milliseconds)
    else:
        await asyncio.sleep(milliseconds / 1000)


class FakeActuator:
    def __init__(self):
        self.active = False

    def start(self):
        self.active = True
        print("- actuator 啟動")

    def stop(self):
        self.active = False
        print("- actuator 回到安全狀態")


async def slow_operation(actuator):
    actuator.start()
    try:
        print("- 慢速操作開始，預計 2 秒")
        await asyncio.sleep(2)
    finally:
        actuator.stop()


async def failing_operation(actuator):
    actuator.start()
    try:
        await sleep_ms(50)
        raise OSError("模擬感測器斷線")
    finally:
        actuator.stop()


async def main():
    print("實驗 8A：timeout")
    actuator = FakeActuator()
    try:
        await asyncio.wait_for(slow_operation(actuator), 0.2)
    except asyncio.TimeoutError:
        print("- 已收到 TimeoutError，不宣稱操作成功")
    print("- timeout 後 active={}".format(actuator.active))

    print("\n實驗 8B：錯誤注入")
    try:
        await failing_operation(actuator)
    except OSError as error:
        print("- 已記錄錯誤：{}".format(error))
    print("- 例外後 active={}".format(actuator.active))


if __name__ == "__main__":
    asyncio.run(main())
