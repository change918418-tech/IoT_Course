# 光照紅燈警示：操作完整性與控制權

> 本講義以目前 `refactor/architecture-foundation` 分支的 P1 實作為準：`SensorSnapshot`、`CommandService`、`LedController` 已整合按鈕、Web、MQTT 與光感來源。舊版 token／多入口設計保留作歷史比較，不可與目前程式介面混用。

歷史紀錄中的 `feature/light-led-alert` 與 `light-led-alert-validated-20261006` 只保存舊版紅閃驗收背景；目前部署基準是 `refactor/architecture-foundation` 的 P1 commit `defafb6`。舊版驗證只針對紅閃功能，不代表全系統效能已驗證。
公開 `config.example.py` 的示例門檻為 1000／1100；本機私人 `config.py` 可保留依裝置校準的 `LIGHT_ALERT_TRIGGER_ADC = 500`，部署時不得用公開範例覆蓋私人 WiFi／密碼或校準值。

## 操作規則與討論結論

> **課堂必須強調：紅閃五次完成，不表示已經允許下一次警示。必須在警示結束後，先讀到 ADC ≥ 1100，再降至 ADC < 1000，才會再次紅閃五次。一直遮光或只回升到 1050，都不會重新觸發。**

### 再次觸發的操作順序

1. 遮光，使 ADC **低於 1000**，觸發紅閃五次。
2. 等五次閃爍結束，LED 恢復原狀。
3. 移開遮擋或增加光照，確認網頁 ADC **至少達到 1100**，保持約一秒，讓背景任務有機會取樣。
4. 再遮光，使 ADC **低於 1000**，才會再次紅閃五次。

「保持約一秒」是方便課堂操作與觀察的建議，不是程式要求持續一秒；實際條件是警示結束後的背景取樣曾讀到解除閾值。若只在紅閃期間變亮、結束時又變暗，不會重新允許觸發。網頁每秒刷新，顯示值是觀察輔助，實際判斷由背景任務執行。

| 依序讀到的 ADC（第一次警示已完成） | 是否再次紅閃 | 原因 |
|---|---|---|
| 500 → 600 → 500 | 否 | 持續偏暗，沒有解除 |
| 500 → 1050 → 500 | 否 | 1050 未達到 1100 |
| 500 → 1100 → 1000 | 否 | 已重新允許，但 1000 並非「低於 1000」 |
| 500 → 1100 → 999 | 是 | 先達解除閾值，再低於觸發閾值 |
| 500 → 1500 → 500 | 是 | 完成變亮解除，再變暗觸發 |

這是**遲滯（hysteresis）**：用不同的觸發與解除閾值，避免數值在 1000 附近波動時反覆警示。`armed` 在觸發後設為 false，只有警示結束後讀到 ADC ≥ 1100 才回到 true；紅閃結束本身不會把 armed 重設。

教室與家中的光照不同，移開遮擋不一定能使 ADC 達到 1100。因此「家中可反覆觸發，教室卻只閃一次」可能是尚未解除，不表示版本錯誤。本次使用者已確認原因即為未考慮重新允許的條件；如需調整閾值，應另依實際明／暗 ADC 值校準。

ADC 嚴格低於 1000 時，保存 LED 正常色碼與亮滅狀態，紅亮 300 ms、全滅 300 ms，重複五次，約 3 秒後恢復。持續偏暗只警示一次；警示結束後讀到 ADC >= 1100 才重新允許下一次低於 1000 的警示。開機已偏暗會觸發一次。警示期間跨越亮／暗閾值不累積待播警示。

討論最初提出「紅燈警示覆蓋輸出，但接受改色並更新背景選擇，結束顯示最新選擇」。此作法可以避免真的插入綠燈，卻讓使用者按了按鈕看不到立即反應，且不再嚴格恢復原先狀態。使用者提出「紅閃 3 次、變綠、再紅閃 2 次」的混淆問題，要求將五次閃爍視為 atomic operation，最後確認：完整警示期間拒絕一般改色、不排隊、完成後恢復原狀。

這裡 atomic 的意思是應用層控制權完整：一般操作不能插入警示、正常狀態不被改寫。不是 CPU 的一条原子指令、資料庫交易，也不是把三個 GPIO 同時硬體切換；亮滅各次更新仍依序寫 GPIO。不可用停用中斷或同步 sleep 阻塞全系統 3 秒。例外／取消與系統關閉可中止五次序列，清理時優先安全熄燈。

## 為何不用等待式鎖

若按鈕呼叫 `await lock.acquire()` 等待警示完成，按下操作會被延後執行，違反「拒絕、不排隊」。目前由 `CommandService.submit()` 同步送入 `LedController`；警示一旦受理即設為 reserved，後續改色立即回覆 `rejected / busy`，不等待改色佇列。

保證的前提是所有 LED 輸出都經過同一個 `LedController.run()`，且受理與owner在目前單一 `uasyncio` 事件迴圈執行。同步受理段沒有 await，其他協程不能在預約檢查與入列之間插入；若日後加入執行緒、IRQ 或直接操作 LED Pin，必須重新設計同步機制。Python 的私有命名只是介面約定，不是權限隔離。

## 呼叫鏈與狀態生命週期

1. `main()` 建立 `SensorSnapshot`、`LedController`、`CommandService`，並安排唯一的 `led_controller.run()` owner task。
2. `light_sensor_task()` 每 50 ms 讀 ADC；先更新 `SensorSnapshot`，只有讀值有效且 `armed=true`、低於 `LIGHT_ALERT_TRIGGER_ADC` 時，才呼叫 `CommandService.submit('low_light_alert', 'light')`。
3. `CommandService` 產生 request ID，交給 `LedController.submit_command()`；警示受理時立即設定 `_reserved=true`，清除尚未執行的一般命令並回覆其 `alert_started`。
4. owner 取到警示後建立 `_effect`，保存 `(_desired_color, _enabled)`；依 `LIGHT_ALERT_ON_MS`、`LIGHT_ALERT_OFF_MS` 與 `LIGHT_ALERT_BLINK_COUNT` 推進紅色 4／全滅 0。
5. 警示完成後恢復保存的正常狀態，將 receipt 標為 `executed`，再解除 reserved；GPIO 只由 owner 寫入。
6. `armed` 仍由光照 producer 管理：警示後讀到 `LIGHT_ALERT_RESET_ADC` 以上才重新允許下一次低光警示。
7. `main()` 清理呼叫 `request_stop()`；owner 的 `finally` 取消未完成結果、熄燈並設定 stopped Event。下次重啟建立新物件。

正常色碼、快照、effect 與 armed 都只在 RAM，不寫 Flash。警示期間取樣持續，但不重新允許或排隊警示；完成後只有再次取樣到解除閾值才 rearm。閾值由裝置 `config.py` 決定，公開範例為 1000／1100，私人裝置可保留已校準值。

`LightSensor.read()` 失敗時保留 last-good value，但 `light_sensor_task()` 會檢查 `last_error`，未知或失敗讀值不提交警示命令。閃爍時間是非同步設定值，受其他協程影響，非硬體精準 3 秒。

## 各操作入口

| 入口 | 警示期間的處理 |
|---|---|
| 實體按鈕1 | `button1_task` 呼叫 `CommandService.submit('cycle', 'button1')`；警示預約或執行中回 `busy`，不排隊。 |
| 網頁按鈕1 | 由 `/api/led/status` 快照顯示 `alert_active`；前端停用只屬提示，後端仍由 CommandService／LedController 驗證。 |
| POST /api/led/toggle | 透過同一個 CommandService；接受回 HTTP 202，busy 回 409，queue full 回 429，未初始化／停止回 503。 |
| MQTT 改色處理 | `MqttManager` 的同步 callback bridge 解析 `led:4`／`led=4`，交給 CommandService；桌面 adapter 已驗證，真 Broker／ESP32 尚未端到端驗證。 |
| 系統清理 | `LedController.request_stop()` 停止受理；owner `finally` 取消未完成效果並寫入安全輸出 0。 |

前端若資料連接失敗，停用 LED 按鈕並標示狀態未知。伺服器 busy 回覆後保持停用，下一次資料刷新且警示已結束才重新啟用。正常色碼／is_on API 表示保存的正常狀態，警示時並非當下红亮／全滅的 GPIO 值。

## 替代方案與優劣

| 方案 | 優點 | 缺點與本次是否採用 |
|---|---|---|
| 警示期間立即拒絕、不排隊 | 五次序列完整、恢復原狀；操作結果明確且記憶體小 | 約 3 秒無法改色，需要提示；本次採用 |
| 警示覆蓋，保存最後改色意圖 | 紅閃不中斷；最後選擇不丟失 | 按下無立即視覺反應，完成後不恢復原狀；未採用 |
| FIFO 排隊、警示後逐一執行 | 每個指令都有機會執行 | 延遲、可能突然連續換色，需要佇列上限與過期策略；未採用 |
| 等待式 mutex／Lock | 可協調共同資源，不必每次立即拒絕 | await 鎖會延後改色，違反本次不排隊語義；鎖本身不定義 UX、優先權及取消政策；未採用 |
| 手動操作優先，中止紅閃 | 使用者可立即掌控 LED | 五次警示可能不完整，需說明中止並防止保存狀態覆蓋新操作；未採用 |
| 任意操作直接寫 GPIO | 程式最少 | 紅／綠插入混淆、恢復競爭；不可滿足需求 |
| 單一 LED 工作任務＋命令佇列 | 控制權集中，已實作忙碌拒絕、警示預約、回應及期限；目前由 `LedController` 採用 |

## 部署、測試與恢復

需上傳 `main.py`、`tasks.py`、`web_server.py`、`index.html`、`hardware/led.py`、`hardware/button.py`、`hardware/sensors.py`、`communication/mqtt_client.py`、`services/command_service.py`、`services/led_controller.py`、`services/sensor_snapshot.py` 與裝置私人 `config.py`。`config.py` 的 WiFi／密碼必須保留，只同步非機密設定；不要部署 `mdy_01/`、`mdy_02/` 或 `lib_backup/`。重啟載入新 HTML 與服務，再刷新瀏覽器。

實機驗收：先選藍色，再遮光確認紅閃五次恢復藍；警示中按實體／網頁按鈕確認不變色且不延後執行；放開後重新按確認可改色；原先熄滅時警示完成也熄滅；持續暗不重複，變亮到1100以上後再遮暗可重觸發；期間刷 RFID、觸發 PIR 音樂、網頁刷新皆應繼續。中斷時確認熄燈。

目前桌面驗證為 Python 33/33、`node tests/test_led_polling.cjs` 與 `node tests/test_rfid_ui.cjs` 通過；涵蓋 owner、AUTO 警示恢復、MANUAL 拒絕、last-good snapshot、未知光感不提交警示、bounded queue、request ID、Web command result 與 MQTT command adapter。這些不是 ESP32 GPIO、實際時間、真 Broker 或硬體電氣驗證。

回復到原已確認的功能，乾淨工作目錄可執行：

```powershell
git switch -c restore-before-light-alert pir-music-web-validated-20261006
```

再部署原應用檔案。Git 不恢復私人 `config.py`；若回復舊版，必須同步使用該版本的 `main.py`、`tasks.py`、`web_server.py`、服務介面與公開配置欄位，並保留目前私人 WiFi／密碼。

## 已知待觀測事項與版本保存

使用者回報移動偵測、實體按鈕等功能偶有卡鈍感受，尚未詳細觀測。未取得可重現步驟、時間量測或日誌，根因與是否和本次警示有關皆未確認，也尚未修正。依使用者指示本次先保存版本，後續再調查；不宣稱所有任務即時性或系統效能已正常。

目前 P1 回合已以 33/33 Python 測試、兩組 Node 前端測試與指定檔案 `py_compile` 驗證；仍未進行 ESP32 實機、真 Broker、外部訂閱者或硬體 GPIO 電氣驗證。

要取回此次紅閃確認版，可在乾淨工作目錄執行：

```powershell
git fetch origin --tags
git switch -c restore-light-alert light-led-alert-validated-20261006
```

再部署到 ESP32，私人配置另行保留。前一個 PIR 音樂網頁確認版標籤也保留，可供後續比較；切換 Git 不會自動更新裝置 Flash。
