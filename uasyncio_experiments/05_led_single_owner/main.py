"""實驗 5：所有 producer 經 CommandService，由唯一 owner 寫 RGB GPIO。"""

import uasyncio as asyncio

from hardware.led import RgbLed
from services.command_service import CommandService
from services.led_controller import LedController


async def wait_result(service, request_id, timeout_ms):
    elapsed = 0
    while elapsed <= timeout_ms:
        result = service.result(request_id)
        if result is not None and result["status"] not in (
                "accepted", "executing"):
            return result
        await asyncio.sleep_ms(20)
        elapsed += 20
    return {"request_id": request_id, "status": "timeout", "reason": None}


async def run_demonstration(service):
    cycle = service.submit("cycle", "experiment5")
    print("[提交 cycle]", cycle)
    print("[cycle 結果]", await wait_result(
        service, cycle["request_id"], 1000))

    effect = service.submit("green_flash_alert", "experiment5")
    print("[提交綠閃]", effect)
    rejected = service.submit("cycle", "experiment5_during_effect")
    print("[效果期間再提交 cycle]", rejected)
    print("[綠閃結果]", await wait_result(
        service, effect["request_id"], 3000))
    print("[Controller snapshot]", service.snapshot())


async def main():
    controller = LedController(RgbLed())
    service = CommandService(controller)
    owner_task = asyncio.create_task(controller.run())
    print("實驗 5：producer 不得直接呼叫 RgbLed.write()")
    try:
        await run_demonstration(service)
    finally:
        service.request_stop()
        await service.wait_stopped()
        await owner_task
        print("[清理] owner 已停止，LED 已關閉")


if __name__ == "__main__":
    asyncio.run(main())
