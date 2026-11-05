# ESP32 實機部署與執行紀錄

## 基本資訊

- 執行日期：2026-11-05；各實驗執行秒數由序列控制程式量測，整批作業的精確開始時間未另行記錄。
- 紀錄完成時間：2026-11-05 00:31:12 +08:00。
- 開發板：Generic ESP32-S3，Windows USB 序列埠 `COM9`。
- 韌體：MicroPython v1.26.1（2025-09-11）。
- 程式版本：實機執行時 `uasyncio_experiments/` 尚未提交；本報告與實驗程式同批納入 Git，實際 commit hash 由 Git 歷史查詢。
- 裝置設定：沿用 ESP32 現有 `config.py`；本紀錄不保存 WiFi SSID、密碼或其他私人設定。
- 接線：沿用裝置現有接線；本次未改接線，沒有新增接線照片。

## 部署結果

十個實驗以原目錄名稱部署到：

```text
/uasyncio_experiments/
├── README.md
├── 01_coroutine_interleaving/main.py
├── 02_button_debounce/main.py
├── 03_sensor_snapshot_periods/main.py
├── 04_pir_event_speaker/main.py
├── 05_led_single_owner/main.py
├── 06_mqtt_async/main.py
├── 07_rfid_async/main.py
├── 08_timeout_cleanup/main.py
├── 09_task_cancellation/main.py
└── 10_web_async_control/main.py
```

另外部署並校驗實驗十使用的 Web 靜態資源：

```text
/assets/uplot/1.6.32/uPlot.min.css
/assets/uplot/1.6.32/uPlot.iife.min.js
/assets/uplot/1.6.32/LICENSE
```

每個檔案上傳後均比較位元組數與 32-bit rolling checksum。11 個實驗檔案及 3 個 Web 資源全部相符。根目錄 `/main.py` 在部署前後皆為 7,142 bytes、checksum `2191954119`，未被覆蓋。

| 檔案系統項目 | 部署前 | 實驗部署後 |
|---|---:|---:|
| 總容量 | 14,680,064 bytes（14.00 MiB） | 14,680,064 bytes（14.00 MiB） |
| 可用空間 | 11,649,024 bytes（11.11 MiB） | 11,419,648 bytes（10.89 MiB） |
| 本次減少 | — | 229,376 bytes |

## 實驗結果

無限循環實驗使用固定觀察窗口，窗口結束後以 `KeyboardInterrupt` 停止，再進行 soft reboot。這類 `KeyboardInterrupt` 是測試控制動作，不列為程式自行失敗。

| 實驗 | 結果 | 實機證據與分析 | 未驗證／限制 |
|---:|---|---|---|
| 1 | 通過 | 1.800 秒自然結束；`fast`、`slow` 在 `await` 間交錯，最後輸出 `all done`。 | 無。 |
| 2 | 部分驗證 | 6.144 秒內 heartbeat 由 0 持續到 5，證明三個按鈕 task 等待時 event loop 未阻塞。 | 未實際按下三個按鈕，去彈跳、單次按下及釋放訊息尚未實機驗證。 |
| 3 | 通過降級路徑 | OLED 初始化回報 `ETIMEDOUT` 後改用序列埠；DHT 讀得 24～25°C、69%，光感為 4095；snapshot 每秒輸出且 sequence 持續增加，DHT 約每兩秒更新。 | OLED 實際顯示未成功；需檢查 I2C 接線、位址或 OLED 模組。 |
| 4 | 部分驗證 | PIR GPIO 6 與喇叭 PWM GPIO 21 初始化成功；8.113 秒內狀態持續為 ready／idle，PIR 保持低電位且 event loop 持續輸出狀態。 | 觀察期間沒有移動事件，因此 Event 通知、旋律播放及事件後重新武裝尚未驗證。 |
| 5 | 通過 | 2.997 秒自然結束；cycle 由 accepted 轉為 executed；綠閃期間再次提交 cycle 得到 rejected／busy；綠閃完成為 executed；停止時輸出 owner 已停止且 LED 已關閉。 | 未以外部儀器量測 GPIO 電位；控制 receipt 與清理輸出已驗證。 |
| 6 | 通過 | 延長重跑後 22.778 秒自然結束；WiFi 取得 IP，MQTT 連線、訂閱、發佈成功，並由 callback 收到同一筆教學訊息；最後輸出 MQTT 已斷線與清理完成。 | 僅驗證當次網路與公開 Broker；未注入斷網或 Broker timeout。 |
| 7 | 未完成驗收 | 30.096 秒內程式維持執行且沒有例外，但只輸出啟動訊息。 | 未放置 RFID 卡；也未在窗口內到達每十次空輪詢的進度訊息，因此無卡輪詢進度與最近五筆紀錄均未完成驗收。 |
| 8 | 通過 | 0.536 秒自然結束；timeout 與模擬感測器斷線兩條路徑都執行 `finally`，最後兩次皆為 `active=False`。 | 使用 FakeActuator，未操作實體 GPIO。 |
| 9 | 通過 | 0.920 秒自然結束；stop request／confirmation 與 `task.cancel()` 都執行清理，兩條路徑最後皆為 `active=False`。 | 使用 FakeOutput，未操作實體 GPIO。 |
| 10 | 通過，另有連線告警 | WiFi、DHT、光感、LED owner 與 Socket Web 啟動；瀏覽器成功渲染完整儀表板。`/api/status`、`/api/data`、`/api/led/status` 皆回 200；POST `/api/led/toggle` 回 202，request 2 隨後為 executed，LED snapshot 由 output 7／enabled 轉為 output 0／disabled。JS 51,081 bytes 與 CSS 1,857 bytes 皆回 200。 | 觀察到 favicon 404、兩次 Web `ECONNRESET`，瀏覽器記錄兩次被中止的 LED status 輪詢；直接 API 驗證仍成功。DHT 後續曾 `ETIMEDOUT`，服務保留上次有效資料。 |

## 實驗十網路設定與介面驗證

ESP32 在實驗十回報：

```text
IP：      192.168.137.176
Netmask： 255.255.255.0
Gateway： 192.168.137.1
DNS：     192.168.137.1
Web：     http://192.168.137.176/
```

API 驗證摘要：

| 請求 | HTTP | 結果 |
|---|---:|---|
| `GET /` | 200 | 儀表板可視化渲染；溫度、濕度、光照、RFID、PIR、LED 區塊均出現。 |
| `GET /api/status` | 200 | `status=ok`。 |
| `GET /api/data` | 200 | snapshot 為 ready；當次為 25°C、69%、光照 3768。 |
| `GET /api/led/status` | 200 | 回傳 RAM controller snapshot。 |
| `POST /api/led/toggle` | 202 | 命令 accepted，request ID 2。 |
| `GET /api/led/commands/2` | 200 | 命令最終為 executed。 |
| `GET /assets/uplot/1.6.32/uPlot.iife.min.js` | 200 | 51,081 bytes。 |
| `GET /assets/uplot/1.6.32/uPlot.min.css` | 200 | 1,857 bytes。 |

命令受理與執行結果分開驗證；HTTP 202 沒有被當成 LED 已完成的證明。

## 尚未完成的實機驗證

1. 實驗二需人工依序按下／釋放三個按鈕。
2. 實驗四需在 PIR 前製造一次穩定移動並確認旋律與重新武裝。
3. 實驗七需檢查無卡輪詢耗時，再以實體卡驗證 UID 與最近五筆上限。
4. 實驗三的 OLED `ETIMEDOUT` 需檢查硬體接線與 I2C 位址。
5. 實驗六尚未執行斷網、Broker timeout 或重連失敗案例。

## 部署與回復

- 執行任一實驗前先停止根目錄 `/main.py`，不可讓正式 task 與實驗同時控制硬體。
- 執行方式：在專案根目錄環境執行選定的 `/uasyncio_experiments/<實驗目錄>/main.py`。
- 停止實驗後進行 soft reboot，即恢復根目錄 `/main.py`。
- 若要移除本次部署，只刪除 `/uasyncio_experiments/`；`/assets/uplot/1.6.32/` 同時供正式 Web 使用，不應在未確認其他使用者前刪除。
