# `uasyncio` 實驗 1～10

本目錄將 `UASYNCIO_STUDENT_MANUAL.md` 的十個實驗拆成可獨立執行的程式。每個子目錄只有該實驗的入口 `main.py`；共用硬體、服務與通訊實作沿用專案根目錄，避免產生第二套 driver。

ESP32-S3 部署、逐項執行證據、網路介面驗證與限制見 [`ESP32_EXECUTION_REPORT.md`](ESP32_EXECUTION_REPORT.md)。

## 實驗索引

| 編號 | 目錄 | 重點 | 執行環境 |
|---:|---|---|---|
| 1 | `01_coroutine_interleaving/` | coroutine、`await`、`gather()`、交錯執行 | 桌面／ESP32 |
| 2 | `02_button_debounce/` | 三個按鈕、非同步去彈跳、等待釋放 | ESP32 |
| 3 | `03_sensor_snapshot_periods/` | DHT、ADC、OLED 不同週期與 snapshot | ESP32 |
| 4 | `04_pir_event_speaker/` | PIR Event、重新武裝、喇叭唯一 consumer | ESP32 |
| 5 | `05_led_single_owner/` | `CommandService`、唯一 LED owner、receipt | ESP32 |
| 6 | `06_mqtt_async/` | WiFi、MQTT 連線、訂閱、發佈與失敗結果 | ESP32＋網路 |
| 7 | `07_rfid_async/` | 非同步 MFRC522、無卡輪詢、最近五筆 RAM 紀錄 | ESP32 |
| 8 | `08_timeout_cleanup/` | timeout、錯誤注入、`finally` 安全清理 | 桌面／ESP32 |
| 9 | `09_task_cancellation/` | stop request、stopped confirmation、取消清理 | 桌面／ESP32 |
| 10 | `10_web_async_control/` | Socket Web、snapshot、LED 非同步命令 | ESP32＋WiFi |

## 執行前規則

1. 先確認開發板型號與 `config.py` 的 GPIO 相容；不要直接假設所有 ESP32 都可使用目前腳位。
2. `config.py` 必須保留自己的 WiFi profiles，不得以 `config.example.py` 覆蓋，也不得提交到 Git。
3. 實驗 2～7、10 會使用真實 GPIO／網路資源。先停止正式 `main.py`，避免兩套 task 同時控制同一硬體。
4. 從專案根目錄執行，讓 `hardware/`、`services/`、`communication/` 與 `lib/` 保持既有 import 路徑。
5. 不部署 `mdy_*/`、`tests/`、`lib_backup/` 或桌面專用範例到 ESP32。
6. 改接任何線路前先斷電；錯誤注入優先使用軟體替身，不在通電時拔接模組。

## 桌面執行

實驗 1、8、9 有 CPython fallback，可直接執行：

```powershell
python -B uasyncio_experiments/01_coroutine_interleaving/main.py
python -B uasyncio_experiments/08_timeout_cleanup/main.py
python -B uasyncio_experiments/09_task_cancellation/main.py
```

桌面結果只證明 coroutine 邏輯，不代表 ESP32 GPIO、韌體或網路已驗證。

## ESP32 執行

使用 Thonny、mpremote 或課堂指定工具，把目前專案依賴與選定實驗放在同一個裝置檔案系統。停止正式程式後，將選定子目錄的 `main.py` 作為「目前腳本」執行。不要同時啟動根目錄正式 `main.py`。

各實驗額外需求：

- 實驗 1、8、9：只需要 MicroPython 的 `uasyncio`。
- 實驗 2：`config.py`、`hardware/button.py`。
- 實驗 3：感測器、OLED、`SensorSnapshot`、SSD1306；字型檔缺少時會降級為內建字型。
- 實驗 4：PIR、無源喇叭及目前的 `tasks.py`、`hardware/`、`communication/`。
- 實驗 5：RGB LED、`CommandService`、`LedController`。
- 實驗 6：有效 WiFi profile、`mqtt_as.py`、可連線的 Broker。公開 topic 可能被其他裝置共用，不放入私人資料。
- 實驗 7：MFRC522、`mfrc522_async.py`、`aiot_tools.py`。
- 實驗 10：目前 Web 部署檔案、`index.html` 與 `assets/uplot/1.6.32/`。此精簡實驗不啟動 MQTT，因此 publish API 會回 unavailable。

## 驗收結果

1. 實驗 1：`fast` 與 `slow` 在等待期間交錯，最後輸出 `all done`。
2. 實驗 2：三個按鈕各只產生一次穩定按下／釋放訊息，heartbeat 持續運作。
3. 實驗 3：光感快速更新、DHT 每兩秒更新、consumer 每秒讀 snapshot；OLED 失敗時序列埠仍繼續。
4. 實驗 4：PIR 穩定觸發後播放一次旋律；取消或例外後 PWM 靜音。
5. 實驗 5：一般命令得到 `executed`；綠閃期間的新命令得到 `busy`；停止後 LED 關閉。
6. 實驗 6：明確輸出訂閱與發佈成功或失敗，不把無連線寫成 published。
7. 實驗 7：無卡時持續輪詢；成功讀卡後最多保留最近五筆 RAM 紀錄。
8. 實驗 8：timeout 與注入例外後 `active=False`。
9. 實驗 9：正常停止與 `task.cancel()` 兩條路徑都完成 cleanup confirmation。
10. 實驗 10：Web 從 RAM snapshot 回應；LED 命令經 service／owner 執行，Web handler 不直接寫 GPIO。
