# HLK-LD2410B 毫米波雷達：MicroPython 快速安裝與開發指南

> 本指南把同目錄的原廠文件整理成「先接線、再驗證、最後寫程式」的操作順序。模組型號以 **HLK-LD2410B** 為準；不要把 LD2410、LD2410C 或其他版本的腳位與通訊協定直接套用過來。

## 先看結論

1. **供電：**VCC 接穩定 **5 V**，電源供應能力 **>200 mA**；GND 必須與 ESP32 共地。
2. **UART：**預設 `256000 baud, 8 data bits, no parity, 1 stop bit`（8N1）。ESP32 的 TX/RX 要交叉接線。
3. **電位：**模組 GPIO 輸出為 **3.3 V**；ESP32 TX 也是 3.3 V。不要把 5 V 直接送進 ESP32 GPIO/UART。
4. **最短驗證路徑：**先用 OUT 腳確認有人／無人，再用 UART 讀取距離與能量資料；首次調參優先使用原廠 PC 工具或 HLKRadarTool APP。
5. **MicroPython：**同目錄的 `ld2410b_micropython.py` 是無第三方依賴的最小驅動，支援正常／工程模式資料解析，以及讀取與設定命令。

---

## 1. 原始文件怎麼分工

| 文件 | 用途 | 何時查閱 |
|---|---|---|
| `HLK LD2410B生命存在感应模组说明书 V1.0 9.pdf` | 產品規格、腳位、安裝、APP、OTA、天線罩與電源要求 | 第一次接線、裝殼、安裝與故障排除 |
| `LD2410B 串口通信协议 V1.08.pdf` | UART 封包格式、ACK、設定命令與資料欄位 | 撰寫 MicroPython driver 或自行調參 |
| `HLKRadarToolAPP 下载链接.pdf` | Android／iOS APP 下載網址 | 用手機藍牙快速設定 |
| `LD2410B V2.44(24073110)固件新增底噪检测功能介绍.pdf` | V2.44 固件的自動底噪檢測流程 | 現場干擾、誤報或難以回到無人狀態 |
| `毫米波传感器天线罩设计指南_海凌科.pdf` | 天線罩材料、厚度、間隙、電源與安裝環境 | 做外殼或固定式裝置前 |
| `ld2410b_micropython.py` | 本指南配套的 MicroPython 驅動範例 | ESP32 應用程式起始點 |

原廠 PDF 保留為查證來源；本指南不取代原廠文件，特別是韌體升級與硬體安裝數值。

---

## 2. 先確認硬體規格

| 項目 | LD2410B 文件值 | 開發上的意義 |
|---|---:|---|
| 工作頻段 | 24–24.25 GHz | 外殼、金屬件與多模組間距會影響偵測 |
| 供電 | DC 5 V，供電能力 >200 mA | 不要由 ESP32 的 3.3 V 腳供電；電源需穩定、低紋波 |
| 平均工作電流 | 約 82 mA | 電源額定值仍以 >200 mA 能力設計 |
| UART | 預設 256000 baud，8N1 | MicroPython `UART` 必須明確設定 baudrate |
| GPIO OUT | 3.3 V；有人高、無人低 | 只需要存在狀態時可不用解析 UART |
| 探測距離 | 約 0.75–6 m，可調 | 實際距離受目標、環境與安裝影響 |
| 探測角度 | 約 ±60° | 天線面要朝向目標區域 |
| 距離解析度 | 預設 0.75 m；協定可設 0.2 m | 距離門與距離值不要混為同一概念 |
| 模組尺寸 | 約 7 mm × 35 mm | 插針孔間距 1.27 mm，安裝前確認治具 |

### 不要直接假設的事項

- 原廠文件明確標示 **模組 GPIO 輸出 3.3 V**，但開發板的 UART 腳位仍要依開發板規格確認；ESP32 端不可接受 5 V 邏輯。
- 「最大距離 6 m」是產品能力說明，不是任何房間、外殼與角度下的保證值。
- 距離值是演算法估算結果；人體姿勢、體型、反射物與安裝方式都會造成波動。

---

## 3. 安裝與接線

### 3.1 建議材料

- HLK-LD2410B 模組
- ESP32 開發板
- 穩定的 5 V 電源，供電能力 >200 mA
- 共地線
- 兩條 UART 訊號線
- USB 線與電腦；若使用 PC 工具，另備 USB-to-TTL 串口工具

### 3.2 ESP32 接線表

以下以「ESP32 使用 UART1」為例，GPIO 編號可依開發板改變：

| LD2410B | ESP32 | 說明 |
|---|---|---|
| `VCC` | 穩定 `5V/VIN` | 不接 ESP32 3.3 V；確認電源共地 |
| `GND` | `GND` | 必接，否則 UART 電位沒有共同參考 |
| `UART_Tx` | ESP32 `RX_PIN` | TX → RX，模組送資料給 ESP32 |
| `UART_Rx` | ESP32 `TX_PIN` | RX ← TX，ESP32 發命令給模組 |
| `OUT` | 任一 3.3 V 相容 GPIO（選配） | 有人高、無人低；只做快速存在狀態時使用 |

**上電前檢查：**VCC 沒有接到 3.3 V、TX/RX 沒有同名直連、GND 已共地、裸露天線沒有碰到金屬或焊錫。

### 3.3 安裝位置

- 天線面朝向要偵測的區域，固定牢靠，避免模組本身晃動。
- 避免正對大面積強反射物；背面也可能透過背瓣感測到移動，必要時用金屬背板或屏蔽罩處理。
- 避免風扇、空調、窗簾、植物等持續運動物體。
- 多個雷達模組彼此至少保持約 **0.5 m**；不要面對面堆疊。
- 模組與外殼建議保留 **3–5 mm**；外殼不可含金屬或遮蔽 24 GHz 的材料。
- 原廠天線罩建議：天線到罩內表面的高度優先約 1 或 1.5 個波長（24.125 GHz 約 12.4 或 18.6 mm）；罩厚度優先依介質中的半波長設計，無法滿足時採低介電材料及較薄厚度。這些數值需以實際材料與外殼實驗確認。

---

## 4. 第一次啟動：先不用寫程式

### 4.1 用 OUT 腳做最小驗證

1. 只接 `VCC`、`GND`、`OUT`。
2. 上電後等待初始化完成；初始化期間的輸出不代表穩定偵測結果。
3. 人進入感測區，`OUT` 應為高；離開並超過「無人持續時間」後，`OUT` 應回低。
4. 若只需要房間有人／無人控制，OUT 腳即可；需要距離、能量、工程模式資料時才接 UART。

### 4.2 用原廠工具讀取與調參

**PC 工具：**

1. 使用 USB-to-TTL 正確接模組 UART，注意 TX/RX 交叉與共地。
2. 工具選擇正確 COM port，設定 `256000` baud、工程模式後連線。
3. 按開始查看即時資料；停止後才能讀取或設定參數。
4. 工具連線時不要同時讓 ESP32 佔用同一組 UART。

**手機 APP：**

- 下載網址：`https://www.hlktech.com/Mobile/App/12.html`
- APP 支援 Android 與 iOS。
- 藍牙廣播名稱通常為 `HLK-LD2410B_xxxx`，`xxxx` 是 MAC 後四碼。
- 預設控制密碼為 `HiLink`；APP 與模組距離建議在 4 m 內。
- 一次只允許一個藍牙主機連線。

### 4.3 韌體升級注意事項

- APP 的 OTA 需在模組約 3 m 內進行，整體約 1–3 分鐘。
- 升級未完成前不可斷電、重啟、強制離開 APP。
- 升級失敗可能造成雷達暫時無法偵測；依原廠流程重新連線並完成升級。
- 自動底噪功能要求 **LD2410B V2.44 (24073110) 或更新固件**，APP 至少 Android V1.5.12／iOS V1.5.4；版本不符時不要把「沒有 Auto 按鈕」誤判成硬體故障。

---

## 5. MicroPython 快速開始

### 5.1 把驅動與應用程式放到板子

將以下檔案上傳至 ESP32：

```text
ld2410b_micropython.py
main.py                 # 你的應用程式
```

驅動只使用 MicroPython 內建的 `machine.UART` 與 `time`，不需要 `upip`、第三方套件或額外 `lib/`。

### 5.2 最小 UART 讀取範例

```python
from ld2410b_micropython import LD2410B

# 依你的 ESP32 接線修改 UART 編號與 GPIO。
radar = LD2410B(uart_id=1, tx=17, rx=16)

while True:
    try:
        data = radar.read(timeout_ms=1000)
        print(
            data["target_state"],
            data["detection_distance_cm"],
            data["moving_energy"],
            data["stationary_energy"],
        )
    except OSError as exc:
        print("radar read error:", exc)
```

### 5.3 只要有人／無人時的應用

不要為了簡單的存在判斷解析所有距離欄位；可直接把 `OUT` 接到 GPIO，或使用 UART 的 `target_state`：

```python
from machine import Pin
from ld2410b_micropython import LD2410B

out = Pin(4, Pin.IN)
radar = LD2410B(uart_id=1, tx=17, rx=16)

while True:
    present = bool(out.value())
    print("present" if present else "absent")
    # 在這裡控制燈、風扇或 Web 狀態。
```

UART 解析適合需要「運動／靜止／距離」的情境；OUT 腳適合低複雜度、低延遲的有人／無人訊號。兩者同時使用時，後端應定義單一狀態來源，避免一個以 UART、另一個以 OUT 各自做決策。

### 5.4 正常模式資料欄位

`radar.read()` 回傳字典：

| 欄位 | 意義 |
|---|---|
| `frame_type` | `0x02`：目標基本資料；`0x01`：工程模式資料 |
| `target_state_code` / `target_state` | 無目標、運動、靜止、運動＋靜止，或底噪檢測狀態 |
| `moving_distance_cm` | 運動目標距離，cm |
| `moving_energy` | 運動目標能量，約 0–100 |
| `stationary_distance_cm` | 靜止目標距離，cm |
| `stationary_energy` | 靜止目標能量，約 0–100 |
| `detection_distance_cm` | 雷達目前採用的探測距離，cm |
| `max_moving_gate` | 工程模式的最大運動距離門 |
| `max_stationary_gate` | 工程模式的最大靜止距離門 |
| `moving_gate_energy` | 工程模式各距離門的運動能量，9 個值 |
| `stationary_gate_energy` | 工程模式各距離門的靜止能量，9 個值 |
| `light_level` / `out_level` | 工程模式附加的光感值與 OUT 狀態 |

後四組工程模式欄位只在 `frame_type == 0x01` 且模組已開啟工程模式時出現。應用程式應以欄位是否存在判斷，不要無條件索引工程模式欄位。

---

## 6. UART 協定重點

### 6.1 資料上報封包

資料封包結構：

```text
F4 F3 F2 F1 | length(2, little-endian) | payload | F8 F7 F6 F5
```

`payload` 開頭包含資料類型與 `AA`：

```text
payload = data_type | AA | target_data | 55 00
```

- `data_type = 0x02`：目標基本資料。
- `data_type = 0x01`：工程模式資料，基本資料後追加距離門能量、光感與 OUT。
- 所有多位元組整數採 **little-endian**。
- UART 讀取必須容忍半包、黏包與雜訊；不要假設一次 `uart.read()` 就是一個完整封包。

### 6.2 設定命令封包與 ACK

命令封包：

```text
FD FC FB FA | length(2, little-endian) | command | value | 04 03 02 01
```

命令流程固定為：

1. 送 `0x00FF` 啟用設定。
2. 等待 ACK 成功。
3. 送實際命令，例如 `0x0061` 讀取參數或 `0x0060` 設定最大距離／無人持續時間。
4. 等待 ACK；ACK 狀態 `0` 才算成功。
5. 送 `0x00FE` 結束設定，讓模組回到工作模式。

`ld2410b_micropython.py` 已提供：

```python
radar.enter_config()
config_payload = radar.read_config()
radar.set_max_distance_and_timeout(
    moving_gate=8,
    stationary_gate=8,
    no_target_seconds=5,
)
radar.exit_config()
```

`read_config()` 與 `set_max_distance_and_timeout()` 會自動執行進入／離開設定流程；不要在應用程式同時發送另一條命令，以免 ACK 被另一個讀取者消耗。

### 6.3 常用命令索引

| 命令 | 用途 | 注意 |
|---:|---|---|
| `0x00FF` | 啟用設定 | 其他設定命令前必須先成功 |
| `0x00FE` | 結束設定 | 讓模組回到工作模式 |
| `0x0060` | 最大運動／靜止距離門、無人持續時間 | 設定會掉電保存 |
| `0x0061` | 讀取目前參數 | 需在設定模式內執行 |
| `0x0062` / `0x0063` | 開啟／關閉工程模式 | 工程模式掉電不保存 |
| `0x0064` | 設定距離門靈敏度 | 可指定單一門或全部距離門 |
| `0x00A0` | 讀取韌體版本 | 升級或排查功能差異先讀它 |
| `0x00A1` | 設定 UART baudrate | 重啟後生效；改完後主機也要改速率 |
| `0x00A2` | 恢復出廠設定 | 會覆蓋目前參數，操作前先備份 |
| `0x00A3` | 重啟模組 | ACK 送完後重啟 |
| `0x00AA` / `0x00AB` | 設定／查詢距離解析度 | `0x0000` 為 0.75 m，`0x0001` 為 0.2 m |
| `0x00AD` / `0x00AE` | 設定／查詢光感輔助控制 | 會改變 OUT 的觸發邏輯 |

需要設定靈敏度、光感輔助控制或底噪功能時，先以 `LD2410B 串口通信协议 V1.08.pdf` 的完整欄位與 ACK 範例為準；不要只複製命令碼而忽略 value 的長度與 little-endian 排列。

---

## 7. 底噪與靈敏度調校

### 7.1 先分辨兩種「底噪檢測」

原廠文件描述兩個不同功能：

- **探測畫面的 Auto：**統計環境底噪後，自動計算並寫入合理的運動／靜止門檻。
- **參數設定頁的底噪檢測：**列出量測值供使用者參考，主要由使用者自行決定參數。

第一次安裝建議使用 APP 的 Auto，流程如下：

1. 更新到相容固件與 APP。
2. 按下 Auto 並確認開始。
3. 倒數約 10 秒期間，人員離開探測範圍。
4. 正式檢測約 60 秒；整段約 70 秒。
5. 檢測完成後再回到場景測試，確認可偵測到人，也能在離開後回到無人。

底噪檢測期間不要有人、動物或持續移動物留在範圍內，否則自動門檻可能把人體能量當成環境噪聲。

### 7.2 調參順序

1. 先調整安裝位置、電源、外殼與反射物，不要先用靈敏度掩蓋硬體問題。
2. 設定最大運動／靜止距離門，先限制不需要的區域。
3. 再調整各距離門靈敏度；值越高越不容易觸發，設為 100 可視為忽略該距離門。
4. 最後調整無人持續時間；它是離開後維持有人狀態的延遲，不是 MicroPython 端的 debounce。
5. 每次只改一項，記錄「安裝位置、門檻、距離、現象」，避免無法回溯。

---

## 8. 建議的 MicroPython 應用架構

### 8.1 最小單任務

適合第一次驗證：

```text
UART read -> parse frame -> print or one output action
```

先確認封包穩定，再加入 LED、Web 或 MQTT。讀取逾時應顯示「雷達未知／通訊逾時」，不要把逾時直接當成「無人」。

### 8.2 uasyncio 應用

適合與其他感測器並行：

```python
import uasyncio as asyncio
from ld2410b_micropython import LD2410B

radar = LD2410B(uart_id=1, tx=17, rx=16)

async def radar_task():
    while True:
        try:
            data = radar.read(timeout_ms=100)
            # 只更新 RAM snapshot；控制策略放在另一層。
            print(data["target_state"], data["detection_distance_cm"])
        except OSError:
            # 短暫失敗可保留尚未過期的 last-good snapshot。
            print("radar unavailable")
        await asyncio.sleep_ms(50)

asyncio.run(radar_task())
```

若同時有 Web／MQTT／LED：

- 只讓一個 task 讀取 UART；其他 task 讀取最近一次快照。
- 讀取 UART 與解析封包不要在每個 Web request 中重複執行。
- 將 `target_state`、距離、最近成功時間、錯誤與韌體版本放入明確的 RAM snapshot。
- 通訊逾時與「有效的無人資料」要分開；前者是未知，不是無人。
- 命令設定與資料讀取不可由多個 task 同時操作同一 UART；需要鎖或單一命令佇列。

---

## 9. 故障排除順序

| 現象 | 優先檢查 |
|---|---|
| 完全沒有輸出 | 5 V 供電、GND、模組是否完成初始化、UART baudrate 是否為 256000 |
| UART 一直 timeout | TX/RX 是否交叉、UART 編號／GPIO 是否正確、是否被 PC 工具或 APP 佔用 |
| 收到亂碼 | baudrate、8N1、共地、電源雜訊、線長與接觸 |
| 一直判定有人 | 持續移動物、強反射物、背面目標、中頻干擾、電源紋波、模組間距 |
| 離開後很久才無人 | 無人持續時間設定；先確認這是預期延遲而非 UART 問題 |
| 靜止人體偵測不到 | 靜止距離門、靜止靈敏度、底噪門檻與安裝角度 |
| APP 找不到模組 | 藍牙是否關閉、距離是否在 4 m 內、是否已有其他主機連線 |
| 更新後功能不一致 | 先讀韌體版本，確認是否達到 V2.44 與 APP 相容版本 |
| 裝入外殼後性能改變 | 外殼是否含金屬、天線罩厚度／間隙、光感是否被遮擋 |

### 建議記錄的診斷資料

```text
module: HLK-LD2410B
firmware: <由 0x00A0 或 APP 取得>
baudrate: 256000
resolution: 0.75m or 0.2m
max moving/stationary gate: <value>
no-target duration: <seconds>
installation: wall/ceiling, height, enclosure
power: 5V, supply capability, cable length
symptom: <observable behavior>
```

---

## 10. 後續開發清單

### 第 1 階段：硬體與協定

- [ ] 5 V、GND、TX/RX 接線檢查完成。
- [ ] OUT 腳有人／無人變化已確認。
- [ ] MicroPython 可收到 `F4 F3 F2 F1` 資料封包。
- [ ] `target_state`、距離、運動／靜止能量解析正確。
- [ ] 已記錄韌體版本與目前雷達參數。

### 第 2 階段：單一應用

- [ ] 定義「有人」、「無人」、「通訊逾時」三種狀態。
- [ ] 對讀取逾時採安全處理，不把未知當無人。
- [ ] 將控制輸出與 UART driver 分層。
- [ ] 用固定測試情境驗證：無人、走近、靜止、離開、背面移動。

### 第 3 階段：整合系統

- [ ] 以單一 task 讀 UART，其他功能讀 snapshot。
- [ ] 設定命令使用單一 owner／命令鎖，避免 ACK 串流混亂。
- [ ] Web／MQTT 顯示最近成功時間與錯誤，不只顯示布林值。
- [ ] 桌面 fake UART 測試半包、黏包、雜訊、錯誤 ACK、逾時與狀態轉換。
- [ ] 最後再做 ESP32 實機長時間與實際安裝位置驗證。

---

## 11. 本次整理的界線

- 本指南與驅動範例依目錄內 5 份原廠 PDF 整理；沒有宣稱已在特定 ESP32、電源、外殼或實際場域完成實機驗證。
- 驅動範例覆蓋常用資料封包與部分設定命令；完整命令欄位、底噪自動配置與藍牙 OTA 仍以原廠 `LD2410B 串口通信协议 V1.08.pdf`、APP 與模組實際韌體為準。
- 原廠文件中的最大距離、角度、天線罩尺寸與電源建議是設計基線；量產或固定安裝前仍需用實際材料、場景與電源做驗證。
