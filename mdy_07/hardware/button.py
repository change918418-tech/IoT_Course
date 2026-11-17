"""
hardware/button.py - 按鈕與去彈跳模組
提供非同步的按鈕監聽與去彈跳功能
"""

from machine import Pin
import uasyncio
import config


class Button:
    """
    非同步按鈕類別，提供穩定的按鈕事件監聽
    """
    
    def __init__(self, pin_num):
        """
        初始化按鈕
        pin_num: GPIO 腳位號碼
        """
        self.pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
        self.pin_num = pin_num
        self.is_pressed = False
        self.press_rejected = False
    
    async def debounce_read(self, debounce_ms=config.BUTTON_DEBOUNCE_MS, reject_if=None):
        """
        非同步去彈跳讀取按鈕狀態
        連續檢測 debounce_ms 毫秒內的穩定狀態
        
        返回: True 表示按鈕已穩定按下，False 表示已穩定釋放
        """
        # 初始狀態
        current_state = self.pin.value()
        stable_count = 0
        
        # 需要連續檢測的次數
        checks_needed = debounce_ms
        
        while stable_count < checks_needed:
            if reject_if is not None and reject_if():
                self.press_rejected = True
            new_state = self.pin.value()
            
            if new_state == current_state:
                stable_count += 1
            else:
                # 狀態改變，重新開始計數
                current_state = new_state
                stable_count = 0
            
            # 每 1ms 檢查一次
            await uasyncio.sleep_ms(1)
        
        # 返回最終穩定狀態（0 = 按下，1 = 釋放）
        return current_state == 0
    
    async def wait_press(self, reject_if=None):
        """
        等待按鈕被按下（非同步）
        返回: 按下時的時間戳
        """
        while True:
            # 輪詢按鈕狀態
            if self.pin.value() == 0:  # 按下（低電位）
                self.press_rejected = bool(reject_if is not None and reject_if())
                # 執行非同步去彈跳
                is_pressed = await self.debounce_read(reject_if=reject_if)
                if is_pressed:
                    self.is_pressed = True
                    return True
            
            await uasyncio.sleep_ms(config.BUTTON_POLL_INTERVAL_MS)
    
    async def wait_release(self):
        """
        等待按鈕被釋放（非同步）
        """
        while self.pin.value() == 0:  # 仍在按下
            await uasyncio.sleep_ms(config.BUTTON_POLL_INTERVAL_MS)
        
        self.is_pressed = False


class ButtonEvent:
    """按鈕事件類別"""
    
    PRESSED = 1
    RELEASED = 2
    
    def __init__(self, button_id, event_type, timestamp=None):
        self.button_id = button_id
        self.event_type = event_type  # PRESSED 或 RELEASED
        self.timestamp = timestamp
        self.event_name = '按下' if event_type == self.PRESSED else '釋放'
    
    def __str__(self):
        return f"按鈕 {self.button_id}: {self.event_name}"
