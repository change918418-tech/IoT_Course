"""實驗 4：PIR producer 透過 Event 通知唯一喇叭 consumer。"""

import uasyncio as asyncio

from hardware.motion import new_motion_state
from hardware.sensors import PirSensor
from hardware.speaker import Speaker
from tasks import music_on_motion_task, pir_monitor_task


async def state_reporter(state):
    while True:
        print("[Motion state]", dict(state))
        await asyncio.sleep(1)


async def main():
    pir_sensor = PirSensor()
    speaker = Speaker()
    motion_event = asyncio.Event()
    motion_state = new_motion_state()
    motion_state["sensor_status"] = "ready"
    motion_state["music_status"] = "idle"

    print("實驗 4：移動需穩定達門檻；Event 只保存待處理旗標")
    try:
        await asyncio.gather(
            pir_monitor_task(pir_sensor, motion_event, motion_state),
            music_on_motion_task(speaker, motion_event, motion_state),
            state_reporter(motion_state),
        )
    finally:
        speaker.deinit()


if __name__ == "__main__":
    asyncio.run(main())
