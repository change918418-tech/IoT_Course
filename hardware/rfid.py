"""MFRC522 非同步讀卡封裝；與單檔教學範例使用相同驅動與格式。"""

import config


def new_rfid_state():
    """RAM 中的最後讀取紀錄與最近5次卡號／時間；重啟即清空。"""
    return {'status': 'starting', 'last_uid': None,
            'last_read_at': None, 'recent_reads': [], 'error': None}


class RfidReader:
    def __init__(self):
        # 延後匯入，缺少驅動／其依賴時可由 main 捕捉並降級。
        from mfrc522_async import MFRC522Async
        from aiot_tools import to_hex_string
        self._to_hex_string = to_hex_string
        self.reader = MFRC522Async(
            sck=config.RFID_SCK_PIN, mosi=config.RFID_MOSI_PIN,
            miso=config.RFID_MISO_PIN, rst=config.RFID_RST_PIN,
            cs=config.RFID_CS_PIN)

    async def read_uid(self):
        """無回應回傳 None；成功保留範例的完整 raw_uid（含檢查碼）。"""
        stat, _ = await self.reader.request(self.reader.REQIDL)
        if stat != self.reader.OK:
            # 驅動 request 將無卡與部分通訊失敗都表示為 ERR，無法區分。
            return None
        stat, raw_uid = await self.reader.anticoll()
        if stat != self.reader.OK:
            raise RuntimeError('RFID anticoll failed')
        return self._to_hex_string(raw_uid)
