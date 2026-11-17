"""
hardware/display.py - OLED 顯示模組（v1.1.3）
職責：負責 OLED 初始化與文字顯示。

I2C、腳位及解析度：
    使用 config.py 的 OLED 設定。

字型：
    使用 bitmap_font_tool + fusion_bdf.12
"""

from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import config

# 字型工具為可選；若不存在，會自動降級為內建字型
try:
    from bitmap_font_tool import set_font_path, draw_text
    _HAS_FONT = True
    # 與 99_All-07.py 相同的字型路徑
    set_font_path('./lib/fonts/fusion_bdf.12')
except Exception:
    _HAS_FONT = False
    draw_text = None


class OledDisplay:
    """
    OLED 顯示封裝：
    - 初始化 I2C + SSD1306
    - 提供 show_two_lines() 介面
    """

    def __init__(self):
        self._i2c = I2C(
            config.I2C_ID,
            scl=Pin(config.I2C_SCL_PIN),
            sda=Pin(config.I2C_SDA_PIN),
            freq=getattr(config, 'OLED_I2C_FREQ_HZ', 400000),
        )
        self._oled = SSD1306_I2C(
            config.OLED_WIDTH, config.OLED_HEIGHT, self._i2c)

        self._has_font = _HAS_FONT
        self._draw_text = draw_text if _HAS_FONT else None

        print(
            "[OLED] OledDisplay 初始化完成"
            "（SCL={}, SDA={}，{}x{}）".format(
                config.I2C_SCL_PIN,
                config.I2C_SDA_PIN,
                config.OLED_WIDTH,
                config.OLED_HEIGHT,
            )
        )

    def clear(self):
        """清空畫面並更新。"""
        self._oled.fill(0)
        self._oled.show()

    def _safe_str(self, value):
        """防呆：避免 None 傳進字型庫。"""
        if value is None:
            return ""
        return str(value)

    def show_two_lines(self, line1, line2):
        """
        顯示兩行文字：
        - line1 顯示在 y=0
        - line2 顯示在 y=16
        自動避免 None 導致 bitmap_font_tool 對 len() 報錯。
        """
        line1 = self._safe_str(line1)
        line2 = self._safe_str(line2)

        self._oled.fill(0)

        if self._has_font and self._draw_text is not None:
            # 使用點陣字型
            self._draw_text(self._oled, line1, 0, 0)
            self._draw_text(self._oled, line2, 0, 16)
        else:
            # 備援：使用內建 8x8 字型
            self._oled.text(line1, 0, 0)
            self._oled.text(line2, 0, 16)

        self._oled.show()

    def show_message(self, msg):
        """顯示單行訊息（除錯用）。"""
        msg = self._safe_str(msg)
        self._oled.fill(0)
        if self._has_font and self._draw_text is not None:
            self._draw_text(self._oled, msg, 0, 0)
        else:
            self._oled.text(msg, 0, 0)
        self._oled.show()
