"""實驗 7：非同步輪詢 MFRC522，保存最近五筆 RAM 紀錄。"""

import uasyncio as asyncio

import config
from communication.wifi import get_current_time
from hardware.rfid import RfidReader, new_rfid_state


async def main():
    reader = RfidReader()
    state = new_rfid_state()
    state["status"] = "ready"
    empty_polls = 0
    print("實驗 7：將卡片靠近 MFRC522；無卡不是致命錯誤")

    while True:
        try:
            uid = await reader.read_uid()
            if uid is None:
                empty_polls += 1
                if empty_polls % 10 == 0:
                    print("[RFID] 尚未讀到卡，task 仍在執行")
            else:
                empty_polls = 0
                date_str, _, time_str = get_current_time()
                record = {
                    "uid": uid,
                    "read_at": "{} {}".format(date_str, time_str),
                }
                state["last_uid"] = uid
                state["last_read_at"] = record["read_at"]
                state["recent_reads"].append(record)
                if len(state["recent_reads"]) > 5:
                    state["recent_reads"].pop(0)
                state["status"] = "ready"
                state["error"] = None
                print("[RFID] 本次={}, 最近五筆={}".format(
                    record, state["recent_reads"]))
        except Exception as error:
            state["status"] = "read_error"
            state["error"] = str(error)
            print("[RFID] 讀取錯誤：{}".format(error))
        await asyncio.sleep_ms(config.RFID_POLL_INTERVAL_MS)


if __name__ == "__main__":
    asyncio.run(main())
