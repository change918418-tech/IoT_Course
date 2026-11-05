"""實驗 6：非同步 MQTT 連線、訂閱、發佈與 timeout 狀態。"""

import uasyncio as asyncio

import config
from communication.mqtt_client import MqttManager
from communication.wifi import connect_wifi


def on_message(topic, message, retained):
    topic_text = topic.decode() if isinstance(topic, bytes) else str(topic)
    message_text = message.decode() if isinstance(message, bytes) else str(message)
    print("[MQTT callback] topic={}, retained={}, message={}".format(
        topic_text, retained, message_text))


async def main():
    print("實驗 6：連線、訂閱後發佈一筆教學訊息")
    ssid, password = await connect_wifi()
    manager = MqttManager(
        ssid,
        password,
        broker=getattr(config, "MQTT_BROKER", "broker.emqx.io"),
    )
    try:
        if not await manager.connect():
            print("[結果] MQTT unavailable；其他實驗不應被宣稱為成功")
            return

        subscribed = await manager.subscribe(
            config.MQTT_TOPICS["subscribe"], callback=on_message)
        print("[訂閱結果]", subscribed)
        if not subscribed:
            return

        device_name = getattr(config, "DEVICE_NAME", "ESP32")
        message = "{} uasyncio experiment 6".format(device_name)
        published = await manager.publish(
            config.MQTT_TOPICS["temp_humi"], message, qos=0)
        print("[發佈結果]", "published" if published else "failed")
        print("[等待] 10 秒內收到的訂閱訊息會由同步 callback 顯示")
        await asyncio.sleep(10)
    finally:
        await manager.disconnect()
        print("[清理] MQTT 已中斷")


if __name__ == "__main__":
    asyncio.run(main())
