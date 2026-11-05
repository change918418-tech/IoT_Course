"""實驗 3：以不同週期更新 DHT、光感與 OLED 共用 snapshot。"""

import uasyncio as asyncio

import config
from hardware.display import OledDisplay
from hardware.sensors import Dht11Sensor, LightSensor
from services.sensor_snapshot import SensorSnapshot


async def dht_producer(sensor, snapshot):
    while True:
        result = sensor.measure()
        snapshot.update_dht(result, sensor.last_error)
        print("[DHT producer] result={}, error={}".format(
            result, sensor.last_error))
        await asyncio.sleep(config.DHT11_POLL_INTERVAL_SEC)


async def light_producer(sensor, snapshot):
    while True:
        value = sensor.read()
        snapshot.update_light(value, sensor.last_error)
        await asyncio.sleep_ms(config.LIGHT_POLL_INTERVAL_MS)


async def snapshot_consumer(snapshot, display):
    while True:
        data = snapshot.snapshot()
        temperature = data["temperature"]
        humidity = data["humidity"]
        light = data["light"]
        print(
            "[Snapshot] status={}, seq={}, T={}({}), H={}({}), L={}({}), age={}ms".format(
                data["status"], data["sample_seq"],
                temperature["value"], temperature["quality"],
                humidity["value"], humidity["quality"],
                light["value"], light["quality"], light["age_ms"],
            )
        )
        if display is not None:
            display.show_two_lines(
                "T:{} H:{}".format(temperature["value"], humidity["value"]),
                "Light:{}".format(light["value"]),
            )
        await asyncio.sleep(config.OLED_UPDATE_INTERVAL_SEC)


async def main():
    snapshot = SensorSnapshot()
    dht_sensor = Dht11Sensor()
    light_sensor = LightSensor()
    try:
        display = OledDisplay()
    except Exception as error:
        display = None
        print("[OLED] 初始化失敗，改用序列埠：{}".format(error))

    print("實驗 3：DHT={}s、光感={}ms、顯示={}s".format(
        config.DHT11_POLL_INTERVAL_SEC,
        config.LIGHT_POLL_INTERVAL_MS,
        config.OLED_UPDATE_INTERVAL_SEC,
    ))
    await asyncio.gather(
        dht_producer(dht_sensor, snapshot),
        light_producer(light_sensor, snapshot),
        snapshot_consumer(snapshot, display),
    )


if __name__ == "__main__":
    asyncio.run(main())
