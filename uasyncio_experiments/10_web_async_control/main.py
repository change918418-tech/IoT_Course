"""實驗 10：啟動輕量 Socket Web、RAM snapshot 與單一 LED owner。"""

import uasyncio as asyncio

import web_server
from communication.wifi import connect_wifi
from hardware.led import RgbLed
from hardware.motion import new_motion_state
from hardware.rfid import new_rfid_state
from hardware.sensors import Dht11Sensor, LightSensor
from services.command_service import CommandService
from services.led_controller import LedController
from services.sensor_snapshot import SensorSnapshot
from tasks import dht11_read_task, light_sensor_task


async def main():
    print("實驗 10：Web 只讀 snapshot，命令由唯一 LED owner 執行")
    await connect_wifi()

    snapshot = SensorSnapshot()
    dht_sensor = Dht11Sensor()
    light_sensor = LightSensor()
    controller = LedController(RgbLed())
    service = CommandService(controller)
    owner_task = asyncio.create_task(controller.run())

    web_server.sensor_snapshot = snapshot
    web_server.command_service = service
    web_server.led_controller = controller
    web_server.motion_state = new_motion_state()
    web_server.rfid_state = new_rfid_state()
    web_server.mqtt_manager = None
    web_server.publish_event = None

    try:
        await asyncio.gather(
            dht11_read_task(dht_sensor, snapshot),
            light_sensor_task(light_sensor, service, snapshot),
            owner_task,
            web_server.web_server_task(),
            web_server.sensor_monitor_task(),
        )
    finally:
        service.request_stop()
        await service.wait_stopped()
        print("[清理] Web 實驗停止，LED 已關閉")


if __name__ == "__main__":
    asyncio.run(main())
