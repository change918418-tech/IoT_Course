# 光照紅燈警示：操作完整性與控制權

> 本講義以目前 P1 單一擁有者實作為準：`SensorSnapshot`、`CommandService`、`LedController` 已整合按鈕1、按鈕3、Web、MQTT與光感來源。舊版token／多入口設計只作歷史比較，不可與目前程式介面混用。

歷史標籤只保存舊版紅閃驗收背景，不代表目前按鈕3綠閃或全系統效能已完成實機驗證。
公開`config.example.py`與本機配置目前依裝置實測採ADC越高越暗、trigger 2000／reset 1500；部署時不得用公開範例覆蓋私人WiFi／密碼。

## 光感極性與本裝置校準

光感模組的分壓接法不同，ADC 方向也會不同，不能一律假設數值越低越暗：

| 設定 | 暗判斷 | 重新允許判斷 | 適用情況 |
|---|---|---|---|
| `LIGHT_DARK_WHEN_HIGH = False` | ADC `< trigger` | ADC `>= reset` | ADC 越低越暗的反向接法 |
| `LIGHT_DARK_WHEN_HIGH = True` | ADC `> trigger` | ADC `<= reset` | ADC 越高越暗 |

本裝置目前實測有光約300、手指遮光約2300，屬於「ADC越高越暗」。目前設定：

```python
LIGHT_ALERT_ENABLED = True
LIGHT_DARK_WHEN_HIGH = True
LIGHT_ALERT_TRIGGER_ADC = 2000
LIGHT_ALERT_RESET_ADC = 1500
```

ADC嚴格高於2000時提交低光警示；警示後必須降至1500（含）以下才重新允許。1501～2000是遲滯區。`/api/data.light_thresholds`回傳相同trigger、reset與dark_when_high，網頁顯示`暗 > 2000`／`亮 ≤ 1500`，Y軸擴展至4095。


## 操作規則與討論結論

> **課堂必須強調：紅閃五次完成，不表示已經允許下一次警示。必須在警示結束後，先讀到 ADC ≤ 1500，再升至 ADC > 2000，才會再次紅閃五次。一直遮光或只降到 1700，都不會重新觸發。**

### 再次觸發的操作順序

1. 遮光，使 ADC **高於 2000**，觸發紅閃五次。
2. 等五次閃爍結束，LED 恢復原狀。
3. 移開遮擋或增加光照，確認網頁 ADC **降至 1500（含）以下**，讓背景任務有機會取樣。
4. 再遮光，使 ADC **高於 2000**，才會再次紅閃五次。

| 依序讀到的 ADC（第一次警示已完成） | 是否再次紅閃 | 原因 |
|---|---|---|
| 2300 → 2200 → 2300 | 否 | 持續偏暗，沒有解除 |
| 2300 → 1700 → 2300 | 否 | 1700 未降至 1500 |
| 2300 → 1500 → 2000 | 否 | 已重新允許，但 2000 並非「高於 2000」 |
| 2300 → 1500 → 2001 | 是 | 先達解除閾值，再高於觸發閾值 |
| 2300 → 300 → 2300 | 是 | 完成變亮解除，再變暗觸發 |

這是**遲滯（hysteresis）**：用不同的觸發與解除閾值避免臨界值附近反覆警示。`armed`在觸發後設為false，只有警示結束後讀到ADC ≤ 1500才回到true；紅閃結束本身不會重設armed。

ADC嚴格高於2000時，保存LED正常色碼與亮滅狀態，紅亮300 ms、全滅300 ms，重複五次後恢復。持續偏暗只警示一次；警示期間跨越亮／暗閾值不累積待播警示。

討論最初提出「紅燈警示覆蓋輸出，但接受改色並更新背景選擇，結束顯示最新選擇」。此作法可以避免真的插入綠燈，卻讓使用者按了按鈕看不到立即反應，且不再嚴格恢復原先狀態。使用者提出「紅閃 3 次、變綠、再紅閃 2 次」的混淆問題，要求將五次閃爍視為 atomic operation，最後確認：完整警示期間拒絕一般改色、不排隊、完成後恢復原狀。

這裡 atomic 的意思是應用層控制權完整：一般操作不能插入警示、正常狀態不被改寫。不是 CPU 的一条原子指令、資料庫交易，也不是把三個 GPIO 同時硬體切換；亮滅各次更新仍依序寫 GPIO。不可用停用中斷或同步 sleep 阻塞全系統 3 秒。例外／取消與系統關閉可中止五次序列，清理時優先安全熄燈。

## 為何不用等待式鎖

若按鈕呼叫`await lock.acquire()`等待效果完成，按下操作會被延後執行，違反「拒絕、不排隊」。目前由`CommandService.submit()`同步送入`LedController`；紅閃或綠閃一旦受理即設為reserved，後續普通命令或另一效果立即回覆`rejected / busy`。

保證的前提是所有 LED 輸出都經過同一個 `LedController.run()`，且受理與owner在目前單一 `uasyncio` 事件迴圈執行。同步受理段沒有 await，其他協程不能在預約檢查與入列之間插入；若日後加入執行緒、IRQ 或直接操作 LED Pin，必須重新設計同步機制。Python 的私有命名只是介面約定，不是權限隔離。

## 呼叫鏈與狀態生命週期

1. `main()` 建立 `SensorSnapshot`、`LedController`、`CommandService`，並安排唯一的 `led_controller.run()` owner task。
2. `light_sensor_task()` 每 50 ms 讀 ADC 並更新 `SensorSnapshot`；`LIGHT_DARK_WHEN_HIGH` 決定低光是高於或低於 `LIGHT_ALERT_TRIGGER_ADC`，只有讀值有效且 `armed=true` 時才提交 `low_light_alert`。
3. `CommandService`產生request ID，交給`LedController.submit_command()`；任一效果受理時立即設定`_reserved=true`，清除尚未執行的一般命令。
4. owner依固定`_EFFECTS`規格建立`_effect`：低光使用紅色4與設定的五次時序，按鈕3使用綠色2、三次、亮滅各300 ms。
5. 效果完成後恢復保存的正常狀態，將receipt標為`executed`，再解除reserved；GPIO只由owner寫入。
6. `armed`仍由光照producer管理：目前高值越暗模式在ADC降至reset（含）以下重新允許。
7. `main()` 清理呼叫 `request_stop()`；owner 的 `finally` 取消未完成結果、熄燈並設定 stopped Event。下次重啟建立新物件。

正常色碼、快照、effect 與 armed 都只在 RAM，不寫 Flash。警示期間取樣持續，但不重新允許或排隊警示；完成後只有取樣跨過目前極性所定義的解除閾值才 rearm。閾值與極性由裝置私人 `config.py` 決定。

`LightSensor.read()` 失敗時保留 last-good value，但 `light_sensor_task()` 會檢查 `last_error`，未知或失敗讀值不提交警示命令。閃爍時間是非同步設定值，受其他協程影響，非硬體精準 3 秒。

## 各操作入口

| 入口 | 警示期間的處理 |
|---|---|
| 實體按鈕1 | 去彈跳期間若`CommandService.busy`為真就記住拒絕；不提交、不排隊，放開後才接受下一次按下。 |
| 實體按鈕3 | 空閒時提交`green_flash_alert`；效果忙碌時消耗該次按壓，不在結束後補做。 |
| 網頁按鈕1 | 呼叫`POST /api/led/toggle`提交cycle；狀態未知或任一效果忙碌時停用。 |
| 網頁按鈕3 | 呼叫`POST /api/led/commands`提交固定`green_flash_alert`；受理後查詢receipt，紅閃／綠閃期間都停用。 |
| LED狀態API | `/api/led/status`的`alert_active`表示占用，`active_effect`讓前端區分低光紅閃與按鈕3綠閃；後端busy仍是權威。 |
| MQTT 改色處理 | `MqttManager`同步callback bridge解析`led:4`／`led=4`，交給CommandService。 |
| 系統清理 | `LedController.request_stop()`停止受理；owner finally取消未完成效果並寫入安全輸出0。 |

前端若資料連接失敗，會同時停用LED按鈕1與按鈕3並標示狀態未知。伺服器busy回覆後保持停用，下一次LED狀態刷新且效果已結束才重新啟用。正常色碼／is_on表示保存的正常狀態，不是效果當下的GPIO輸出。

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

需上傳`index.html`、`main.py`、`tasks.py`、`hardware/led.py`、`hardware/button.py`、`services/command_service.py`、`services/led_controller.py`與裝置私人`config.py`；其他應用檔案應維持同一版本。ESP32的`config.py`須保留WiFi／密碼並加入`BUTTON3_PIN = 16`；不要部署任何`mdy_N/`備份目錄。

實機驗收：先選藍色，分別用實體與網頁按鈕3確認綠閃三次並恢復藍色；綠閃中按按鈕1、再次按按鈕3或觸發低光，確認都不插入或延後。再遮光確認紅閃五次恢復，ADC降至1500（含）以下後再升到2000以上可重觸發。期間RFID、PIR音樂與Web刷新應繼續。

桌面測試涵蓋owner、紅／綠效果互斥、綠閃三次、不同原狀恢復、忙碌按壓消耗、GPIO失敗、Web命令結果與MQTT adapter；這些不是ESP32 GPIO、實際時間、真Broker或硬體電氣驗證。

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
