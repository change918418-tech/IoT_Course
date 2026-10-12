# 專案變更紀錄

本檔案記錄「物聯網軟體架構」教學專案的演變、修改原因、作法與驗證。時間一律使用台灣時間 `Asia/Taipei / UTC+08:00`，日期格式為 `YYYY-MM-DD`，時間格式為 `HH:mm:ss`。新紀錄放在最上方，保留既有歷史，不以最新結論覆蓋舊紀錄。

## 紀錄規則

每次修改程式、設定、測試、部署、文件或版控規則，都必須在同一個 Git commit 更新本檔案。紀錄至少包含：

- 變更 ID、版本或狀態。
- 修正／完成日期與時間，以及紀錄時間；不確定的時間明確註記，不得推估成精確時間。
- 原因類別：`BUG` 或 `需求變更`。
- 現象、原因分析、詳細作法、影響範圍、驗證與限制。
- 關聯檔案、測試方式、部署或回復方法。

`BUG` 表示行為不符合既有預期；`需求變更` 包含新功能、政策調整、文件與流程要求。一件工作若同時包含兩類，拆分紀錄或明確標示各項原因。

Git commit hash 由歷史查詢取得；不要求把包含本紀錄的 commit hash 寫回本紀錄，避免自我引用。既有程式中的 v1.1.x／v1.2 註解不是統一的專案版本，本次開始以 Git commit 與後續 tag 作為版本依據。
## CHG-20261012-026｜同步 LED 講義與裝置私人配置至 P1

- **類別：**需求變更（文件與裝置部署配置同步）。
- **日期／紀錄時間：**2026-10-12 20:44:01 +08:00，工具取得台北時間。
- **原因：**P1 已將舊 `LedService` 介面替換為 `CommandService`／`LedController`，但 `LED_SINGLE_OWNER_GUIDE.md` 與 `LIGHT_LED_ALERT_GUIDE.md` 仍有舊版 token、事件任務、MQTT callback 未接通及部署清單描述；私人 `config.py` 也缺少新的 `LED_CONTROL_MODE` 設定，無法直接以目前 P1 程式配置部署。
- **作法：**更新兩份 LED 講義，將目前實作改以 `SensorSnapshot`、`CommandService`、`LedController`、MQTT callback bridge、命令 receipt、bounded queue、AUTO／MANUAL、Web 快照與目前部署清單為準；未實作的按鈕 3 綠閃保留並明確標示為提案。更新本機私人 `config.py`，新增 `LED_CONTROL_MODE = 'AUTO'`，保留原有 WiFi SSID／密碼及裝置專屬 `LIGHT_ALERT_TRIGGER_ADC = 500` 校準值；公開 `config.example.py` 的 placeholder WiFi 與 1000／1100 範例值不被私人設定覆蓋。
- **影響：**ESP32 可直接上傳目前 P1 程式與本機 `config.py`；WiFi／密碼仍保留。私人 `config.py` 仍被 Git 忽略，不納入 commit、備份或公開文件；`mdy_01/`、`mdy_02/` 與 `lib_backup/` 不屬於 ESP32 部署檔案。
- **驗證：**私人配置匯入檢查確認 `LED_CONTROL_MODE = 'AUTO'` 且 WiFi profiles／裝置專屬 500／1100 閾值未被替換；Python unittest 33/33 通過；`node tests/test_led_polling.cjs`、`node tests/test_rfid_ui.cjs` 通過；指定 Python 檔案 `py_compile` 通過；LED 講義 Mermaid 11.13.0 實際解析 `LED_SINGLE_OWNER_GUIDE.md` 21/21，`LIGHT_LED_ALERT_GUIDE.md` 0 個，共 21/21 通過。未進行 ESP32 實機、真 Broker、外部訂閱者或硬體 GPIO 電氣驗證。
- **部署／回復：**部署 `main.py`、`tasks.py`、`web_server.py`、`index.html`、`hardware/led.py`、`hardware/sensors.py`、`communication/mqtt_client.py`、`services/command_service.py`、`services/led_controller.py`、`services/sensor_snapshot.py`、`config.py` 與必要的 `lib/` 檔案；不要部署 `mdy_01/`、`mdy_02/`、`lib_backup/`。回復時還原兩份講義與 `config.py` 的 `LED_CONTROL_MODE`，並保留私人 WiFi／密碼。

## CHG-20261012-025｜實作 P1 SensorSnapshot、CommandService 與 LedController

- **類別：**需求變更（P1 核心架構改善）。
- **日期／紀錄時間：**2026-10-12 16:53:00 +08:00，工具取得台北時間。
- **原因：**P0 已修復 MQTT callback 與發佈狀態語意，但按鈕、Web、MQTT、光感仍需要以一致的 LED 命令邊界與狀態模型協作；感測資料也需要與硬體讀取解耦，避免 Web／OLED／MQTT 各自讀取或重複觸發感測器。
- **作法：**新增 `services/sensor_snapshot.py`，集中保存溫度、濕度、光照的 last-good value、valid、quality、age、error 與 sample sequence；新增 `services/command_service.py`，產生遞增 request ID 並提供共同命令入口；以 `services/led_controller.py` 取代 `services/led_service.py`，成為唯一 LED GPIO owner，建立 bounded queue／result history、desired／enabled／applied 分離、AUTO／MANUAL 模式、低光警示保存／恢復與命令 receipt。更新 `main.py` 組裝並注入三個核心服務；更新 `tasks.py` 將按鈕、光感與 MQTT 訂閱遷移到 CommandService，DHT／光感 producer 更新 SensorSnapshot，且光感讀值失敗或未知時不提交 LED 警示命令，OLED／MQTT 發佈讀取快照；更新 `web_server.py` 讓 `/api/data` 只讀快照，LED toggle、canonical commands、mode、status、result 路由共用 CommandService。更新 `hardware/sensors.py` 保留感測 last-good 值與錯誤；更新 `config.example.py` 的 `LED_CONTROL_MODE`；刪除舊 `services/led_service.py`。保留 MQTT 既有 `led:4`／`led=4` payload 邊界，未在本次加入重連重新訂閱、權限／TLS、Broker ACK 或 supervisor。
- **輪次備份：**在本回合任何既有程式檔案修改前建立 `mdy_02/`，保存本回合涉及的 `main.py`、`tasks.py`、`web_server.py`、`config.example.py`、`hardware/sensors.py`、`hardware/led.py`、`services/led_service.py` 與既有測試原始版本；未備份私人 `config.py`，未建立或覆蓋 `mdy_03/`。新增的 P1 核心檔案與測試沒有「修改前既有版本」。
- **影響：**四個 LED 命令來源共用 request ID、輸入驗證、有限佇列與結果語意；owner frame 以外不直接寫 GPIO。光感 AUTO 低光警示完成後恢復使用者 desired state，MANUAL 拒絕光感覆蓋；感測失敗不再以 `-1` 覆蓋 last-good value，而由 Snapshot 明確表達品質與年齡，未知光感值也不會觸發控制命令。Web 仍保留舊 LED toggle 與 MQTT wire format，HTTP `202` 僅代表命令已受理。
- **文件：**同步更新 `IOT_ARCHITECTURE_TECH_TREE.md`、`SYSTEM_ARCHITECTURE.md`、`WEB_UI_EXECUTION_GUIDE.md`，將 P1 實作狀態、資料／命令流、歷史 P0 討論與驗收界線分開記錄。
- **驗證：**`python -B -m unittest discover -s tests -v` 通過 33/33；`node tests/test_led_polling.cjs` 通過；`node tests/test_rfid_ui.cjs` 通過；指定 P1 Python 檔案 `py_compile` 通過。桌面 fake GPIO／fake MQTT／Microdot TestClient 已覆蓋單一 owner、AUTO 警示恢復、MANUAL 拒絕、last-good snapshot、未知光感不提交警示、bounded queue、request ID、Web command result 與 MQTT command adapter。Mermaid 11.13.0 實際解析 `IOT_ARCHITECTURE_TECH_TREE.md` 1/1、`SYSTEM_ARCHITECTURE.md` 1/1、`WEB_UI_EXECUTION_GUIDE.md` 12/12，共 14/14 個 Mermaid 區塊通過。未進行 ESP32 實機、真 Broker、外部訂閱者或硬體 GPIO 電氣驗證。
- **部署／回復：**部署 `main.py`、`tasks.py`、`web_server.py`、`hardware/sensors.py`、`hardware/led.py`、`config.example.py`、`services/command_service.py`、`services/sensor_snapshot.py`、`services/led_controller.py`、對應 `tests/` 與文件；不要部署 `mdy_02/`，不要覆蓋私人 `config.py`。回復時以 `mdy_02/` 對應快照還原既有檔案，並移除本回合新增服務／測試；若回復至 P0，需同步恢復 `services/led_service.py` 及其呼叫者契約。

## CHG-20261012-024｜實作 P0 MQTT callback、指令派送與發佈狀態語意

- **類別：**BUG（MQTT 入站 callback 斷路、連線結果未檢查、HTTP 發佈完成語意錯誤）。
- **日期／紀錄時間：**2026-10-12 15:43:08 +08:00，工具取得台北時間。
- **原因：**`lib/mqtt_as.py` 以同步三參數呼叫收訊 callback，但 adapter 原本使用非同步 `on_message()`；訂閱時傳入的 callback 未被保存；MQTT 任務忽略 `wait_connected()`；`POST /api/publish` 將 Event 受理誤報成已完成發佈，且前端只依 HTTP 成功顯示已發布。
- **作法：**修改 `communication/mqtt_client.py`：建立同步 callback bridge、保存並派送訂閱 handler、以連線 callback／Event確認 `wait_connected()`、追蹤發佈 `accepted`／`publishing`／`published`／`failed`／`unavailable`。修改 `tasks.py`：訂閱 callback 維持既有 `led:4`／`led=4` 格式，解析後交給 `LedService.submit()`；發佈任務檢查連線並更新結果。修改 `web_server.py`：`/api/publish` 回傳 JSON 與 HTTP 202／503，新增 no-store 的 `/api/publish/status`。修改 `index.html`：依 JSON status 顯示「已受理」或錯誤，不把 accepted 宣稱成完成。同步更新 `IOT_ARCHITECTURE_TECH_TREE.md`、`SYSTEM_ARCHITECTURE.md`、`WEB_UI_EXECUTION_GUIDE.md`。未修改 `lib/mqtt_as.py`，未提前建立 P1 完整 `CommandService`。
- **輪次備份：**在本回合程式修改前建立 `mdy_01/`，保存 `communication/mqtt_client.py`、`tasks.py`、`web_server.py`、`index.html` 與 `tests/test_mqtt.py` 的修改前版本；不含私人設定與秘密。下次程式修改輪次應使用 `mdy_02/`。
- **影響：**MQTT 入站 LED 指令現在到達既有單一 `LedService.submit()` 受理邊界；HTTP 發佈可區分受理與背景任務最近結果；既有 MQTT payload 格式與 QoS 0 不變。Event 仍是單一旗標，重複觸發可能合併；重連後重新訂閱、完整 P1 `CommandService`、Broker ACK 與權限安全仍未納入。
- **驗證：**MQTT 專項測試 10/10 通過；完整 Python 測試 33/33 通過；`node tests/test_led_polling.cjs` 與 `node tests/test_rfid_ui.cjs` 通過；`python -B -m py_compile communication/mqtt_client.py tasks.py web_server.py tests/test_mqtt.py` 通過；Mermaid 11.13.0 實際解析 `IOT_ARCHITECTURE_TECH_TREE.md` 1/1、`SYSTEM_ARCHITECTURE.md` 1/1、`WEB_UI_EXECUTION_GUIDE.md` 12/12；`git diff --check` 無差異錯誤；桌面 fake MQTT／fake LED 已確認同步 callback、`LedService.submit()` 派送、連線逾時與 HTTP JSON 狀態分層。ESP32 實機、真 Broker、外部訂閱者與斷線重連尚未驗證。
- **部署／回復：**部署 `communication/mqtt_client.py`、`tasks.py`、`web_server.py`、`index.html`，並依專案既有部署清單重啟裝置；不部署 `mdy_01/`。回復時以 `mdy_01/` 對應快照還原上述檔案，或使用 Git 差異回復；不要覆蓋私人 `config.py`。

## CHG-20261012-023｜記錄 P0 MQTT 與 P1 共用命令入口討論及程式輪次備份規則

- **類別：**需求變更（架構決策與版控流程）。
- **日期／紀錄時間：**2026-10-12 15:29:46 +08:00，工具取得台北時間。
- **原因：**兩輪討論釐清IOT架構技術樹P0的MQTT修正邊界，以及是否要提前導入P1的MQTT／Web／按鈕共用命令入口；同時使用者要求未來每一輪程式修改先保存原始版本，依序放入`mdy_01`、`mdy_02`等目錄。
- **討論紀錄：**第一輪確認目前`mqtt_as`以同步方式呼叫`subs_cb(topic, msg, retained)`，但`MqttManager.on_message()`為非同步函式；`MqttManager.subscribe()`忽略傳入callback；MQTT任務忽略`wait_connected()`結果；`POST /api/publish`把事件觸發誤報為資料已發佈。第二輪決定P0只修正callback bridge、指令派送、連線結果及accepted／published／failed語意，保留現行`lib/mqtt_as.py`，並讓MQTT指令進入既有`LedService.submit()`；P1才建立完整`CommandService`，一次遷移按鈕、Web與MQTT，避免P0形成半套第二命令入口。
- **作法：**將上述兩輪討論詳記於`IOT_ARCHITECTURE_TECH_TREE.md`的P0／P1段落；將程式修改前的輪次備份規則加入`GIT_VERSION_CONTROL.md`。第一次程式修改回合使用`mdy_01/`，下一回合使用`mdy_02/`，備份保留相對路徑且排除私人`config.py`與所有秘密。本次只有文件修改，尚未建立`mdy_01/`，也未修改程式。
- **影響：**後續P0實作必須以`LedService.submit()`作為現有單一LED命令受理邊界，不得由MQTT callback直接寫GPIO或複製仲裁政策；P1再引入完整`CommandService`。每一輪程式修改均可由對應`mdy_N/`回復，且封存備份不得部署到ESP32。
- **驗證：**已檢查文件內容與目前P0／P1方案一致；`git diff --check`無差異錯誤；Mermaid 11.13.0實際解析`IOT_ARCHITECTURE_TECH_TREE.md`的1/1個圖表區塊；本次未修改程式，因此不宣稱完成MQTT修正，也未建立`mdy_01/`，未執行程式測試。
- **部署／回復：**本次只納入文件變更，不需上傳ESP32。回復時還原`IOT_ARCHITECTURE_TECH_TREE.md`、`GIT_VERSION_CONTROL.md`與`ChangeLog.md`本次段落；未來程式回合須先備份再修改，回復優先使用對應`mdy_N/`快照。

## CHG-20261012-022｜整理 lib 重複函式庫並建立封存目錄

- **類別：**需求變更（架構與部署結構）。
- **日期／紀錄時間：**2026-10-12 14:49:29 +08:00，工具取得台北時間。
- **原因：**`lib/`同時存在3個MFRC522、2個Queue與2個MQTT實作；多份可替代模組會讓部署選擇、import 路徑與後續架構調整的基線不明。
- **作法：**保留`lib/mfrc522_async.py`、`lib/async_queue.py`與`lib/mqtt_as.py`；建立`lib_backup/`，將`mfrc522.py`、`mfrc522_async_sync.py`、`queue_ns_async.py`與`mqtt_async.py`移入封存。更新`SYSTEM_ARCHITECTURE.md`的目錄、部署清單與選擇理由；未修改目前主流程的import。
- **選擇理由：**RFID保留`mfrc522_async.py`，因`hardware/rfid.py`明確使用`MFRC522Async`及非同步`request`／`anticoll`，且測試契約相同；Queue保留較小且單一責任的`async_queue.py`，兩者目前都無呼叫者，而`queue_ns_async.py`額外含未使用且`task_done()`為空實作的`SimpleQueue`；MQTT保留`mqtt_as.py`，因`communication/mqtt_client.py`明確匯入其`MQTTClient`與`config`，是現行主流程契約。
- **影響：**目前裝置程式的有效函式庫集合只保留上述三個檔案；封存檔不應上傳ESP32。既有RFID、MQTT與桌面測試的import路徑不變；Queue仍未接入目前主流程。
- **驗證：**靜態分析確認現行程式沒有引用移入封存的模組；檢查確認`lib/`保留3個指定模組且`lib_backup/`存在4個封存檔；`python -B -m unittest discover -s tests -v`通過24/24；`git diff --check`無差異錯誤；Mermaid 11.13.0實際解析`SYSTEM_ARCHITECTURE.md`與`IOT_ARCHITECTURE_TECH_TREE.md`共2/2個圖表區塊。未進行ESP32實機部署或讀卡／Broker端到端驗證。
- **部署／回復：**部署時只帶`lib/`內仍被主流程需要的檔案，不上傳`lib_backup/`。回復時可將封存檔移回`lib/`，但恢復任何替代MQTT／RFID實作前必須重新確認import與API契約；不覆蓋私人`config.py`。

## CHG-20261012-021｜以第一性原理重整完整技術樹六問格式

- **類別：**需求變更（教學文件）。
- **日期／紀錄時間：**2026-10-12 13:02:37 +08:00，工具取得台北時間。
- **原因：**既有技術樹已涵蓋物聯網架構能力，但每個節點的欄位名稱使用「使用時機」，未完全對齊使用者要求的「使用前提、使用情境、是什麼、為什麼、做什麼、怎麼做」六問格式；文件開頭也未明確說明技術點／知識點及提案與現況的界線。
- **作法：**重整`IOT_ARCHITECTURE_TECH_TREE.md`標題與導言，明確由物理限制、時間、資源、信任與可驗證性推導A01～H04共32個技術點／知識點；將全部32個節點的欄位統一為六問格式，並補充每一欄的閱讀定義與尚未部署的提案標示原則。未修改韌體、設定、API或測試程式。
- **影響：**學生可依A→H閱讀完整技術樹，逐點回答採用條件、問題情境、概念定義、必要性、責任與實作方式；既有系統架構與程式行為不變。
- **驗證：**已以Mermaid 11.13.0實際解析`IOT_ARCHITECTURE_TECH_TREE.md`的1/1個圖表區塊；已檢查32個節點均具有六個欄位，且不再使用`使用時機`欄位；`git diff --check`無差異錯誤；`python -B -m unittest discover -s tests -v`通過24/24。未進行ESP32實機驗證。
- **部署／回復：**只需納入`IOT_ARCHITECTURE_TECH_TREE.md`與`ChangeLog.md`，不需重新上傳ESP32。回復時還原這兩個文件的本次變更；不應回復或覆蓋私人`config.py`。

## CHG-20261012-020｜縮短PIR重新武裝等待

- **類別：**BUG（實機已能偵測並播放，但下一次移動需等待過久）。
- **日期／紀錄時間：**2026-10-12 01:52:10 +08:00，工具取得台北時間。
- **原因：**上一版`PIR_LOW_REARM_MS = 5000`要求PIR低電位連續穩定5秒後才重新武裝，因此一次事件結束後的下一次偵測會顯得遲鈍。
- **作法：**將私人`config.py`與公開`config.example.py`的`PIR_LOW_REARM_MS`由5000調整為1500 ms；`tasks.py`缺少設定時的預設值同步調整為1500。保留100 ms輪詢與200 ms高電位確認，仍以穩定低電位重新武裝，避免退回500 ms時較容易出現同一次靠近重複觸發的問題；同步更新兩份架構文件。
- **影響：**PIR在低電位穩定1.5秒後可再次偵測；短暫低／高抖動仍不會重新計數。1500 ms是防重複與回應速度的折衷值，若實機模組仍有分離脈衝，需再依波形或實測調整。
- **驗證：**PIR專項測試6/6通過；完整Python測試24/24通過；前端LED／RFID／移動狀態測試通過；指定Python檔案`py_compile`通過；Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過；`git diff --check`無差異錯誤。測試驗證穩定低電位重新武裝後仍可再次觸發；未進行ESP32實機驗證。
- **部署／回復：**重新上傳`tasks.py`與私人`config.py`並重啟ESP32；`config.example.py`、文件與`ChangeLog.md`供版控／教學使用，不上傳到裝置。回復時將兩個裝置檔案的`PIR_LOW_REARM_MS`改回5000。

## CHG-20261012-019｜讓移動／喇叭狀態獨立更新網頁

- **類別：**BUG（PIR已觸發並播放音樂，但網頁的移動狀態未及時更新）。
- **日期／紀錄時間：**2026-10-12 01:40:10 +08:00，工具取得台北時間。
- **原因：**前端原本只透過`GET /api/data`取得移動狀態；該API同時讀取DHT與ADC，慢感測或回應延遲時，PIR／喇叭RAM快照也會被一起延遲。此項以程式路徑分析定位，未宣稱已在ESP32重現每一個阻塞時序。
- **作法：**新增`GET /api/motion/status`，只複製`motion_state`快照並回`Cache-Control: no-store`；`index.html`新增獨立的`updateMotionStatus()`／`pollMotionStatus()`，每1000 ms輪詢且同一時間只保留一筆請求。`/api/data`仍保留`motion`欄位以維持既有API相容性。
- **影響：**PIR偵測時間、去抖與喇叭播放邏輯不變；網頁移動文字、最近5次紀錄、次數與喇叭狀態不再依賴完整感測資料API完成。同步更新前端測試、API測試、`WEB_UI_EXECUTION_GUIDE.md`與`SYSTEM_ARCHITECTURE.md`。
- **驗證：**前端RFID／移動狀態測試與LED輪詢測試通過；完整Python測試24/24通過，指定檔案`py_compile`通過，Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過，`git diff --check`無差異錯誤。測試確認獨立API快照可更新移動文字與喇叭狀態。未進行ESP32實機驗證。
- **部署／回復：**重新上傳`index.html`與`web_server.py`並重啟ESP32，使`HTML_PAGE`重新載入；不需上傳`tasks.py`或`config.py`。若需回復，還原上述兩個程式檔案與前端／API測試、文件變更。

## CHG-20261012-018｜修正MicroPython MQTT例外診斷遮蔽原始錯誤

- **類別：**BUG（MQTT連線錯誤被缺少的`traceback`模組再次覆蓋）。
- **日期／紀錄時間：**2026-10-12 01:30:05 +08:00，工具取得台北時間。
- **原因：**`mqtt_client.py`捕捉到`[Errno 104] ECONNRESET`後匯入桌面Python的`traceback`；ESP32的MicroPython環境沒有該模組，因此原始網路錯誤被替換成`no module named 'traceback'`並冒泡到`main.py`。`main.py`最外層也有相同不相容匯入。
- **作法：**移除`communication/mqtt_client.py`與`main.py`的`traceback`匯入／呼叫；連線失敗改以`type(e).__name__`與`str(e)`輸出原始例外並回傳`False`，主程式致命錯誤路徑也採相容字串輸出。新增MQTT測試替身，確認`OSError(104, 'ECONNRESET')`不再被`ModuleNotFoundError`遮蔽。
- **影響：**ESP32將看到類似`OSError: [Errno 104] ECONNRESET`的真正連線錯誤，MQTT初始連線仍依`main.py`既有3次嘗試與其他功能繼續運行政策處理；未改變Broker、TLS或重連策略。
- **驗證：**MQTT例外回歸測試通過；完整Python測試24/24通過，Node前端測試通過，指定Python檔案`py_compile`通過，Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過。測試以fake MQTT client重現`OSError(104, 'ECONNRESET')`並確認回傳`False`且不再拋出`ModuleNotFoundError`。未進行ESP32實機或Broker端到端驗證。
- **部署／回復：**重新上傳`communication/mqtt_client.py`與`main.py`，重啟ESP32；若只需恢復診斷文字，還原這兩個檔案即可。`lib/mqtt_as.py`與私人`config.py`不需因本修正變更。

## CHG-20261012-017｜延長PIR穩定低電位重新武裝時間

- **類別：**BUG（實機仍出現同一次靠近的兩次事件）。
- **日期／紀錄時間：**2026-10-12 01:22:04 +08:00，工具取得台北時間。
- **原因：**上一版非同步狀態機只要求低電位穩定500 ms；實際PIR模組在同一次手部靠近期間可能產生間隔超過500 ms但仍屬同一反應的第二個高脈衝，因此狀態機已重新武裝後再次計數。
- **作法：**將`PIR_LOW_REARM_MS`由500調整為5000，保留100 ms非同步取樣與200 ms穩定高電位確認。只有低電位連續穩定5秒才重新武裝，避免PIR模組的分離脈衝被當成兩次移動；同步更新私人設定指引、公開設定範例、測試時序與兩份文件。
- **影響：**一次移動事件結束後，需持續無移動5秒才允許下一次事件；5秒內的第二次真實移動會合併為同一事件。5秒是目前針對使用者實機現象的保守參數，仍可依PIR模組輸出調整。
- **驗證：**PIR／音樂測試6/6通過；完整Python測試23/23通過；Node前端測試通過；指定Python檔案`py_compile`通過；Mermaid 11.13.0解析13/13通過。測試涵蓋tick回繞、短暫低／高抖動、穩定低5秒重新武裝與最近5筆歷史。未進行ESP32實機驗證。
- **部署／回復：**更新`tasks.py`，並在裝置私人`config.py`將`PIR_LOW_REARM_MS`改為5000；不可用公開範例覆蓋私人WiFi設定。重啟ESP32後再觀察實際PIR；回復時將此參數還原為500（若要回復上一版狀態機行為，也需同步還原`tasks.py`）。

## CHG-20261012-016｜實作PIR非同步穩定邊緣防抖

- **類別：**需求變更（PIR事件判斷改善）。
- **日期／紀錄時間：**2026-10-12 01:09:45 +08:00，工具取得台北時間。
- **原因：**固定`PIR_RETRIGGER_COOLDOWN_MS = 5000`只能以時間抑制重複事件，無法判斷移動是否真正結束；它可能吞掉5秒內真正分開的第二次移動。使用者要求實作較好的非同步防抖機制。
- **作法：**`tasks.py`改用非阻塞穩定邊緣狀態機：每100 ms取樣，PIR高電位連續200 ms才觸發一次；觸發後保持未武裝，低電位連續500 ms才重新武裝；短暫低／高抖動不會重新計數。新增`PIR_HIGH_DEBOUNCE_MS`、`PIR_LOW_REARM_MS`與`MOTION_DETECTED_HOLD_MS`設定，移除固定冷卻參數；`MOTION_DETECTED_HOLD_MS`只保留網頁顯示保持語意。更新`config.example.py`、PIR測試與兩份文件。
- **影響：**一次手部靠近的PIR訊號必須先穩定高才計數；同一次事件內的高電位持續或短暫低／高抖動不會重複觸發。下一次事件必須先完成穩定低重新武裝。輪詢由500 ms改為100 ms，增加取樣頻率但仍使用uasyncio非同步睡眠，不阻塞其他任務。
- **驗證：**PIR／音樂測試6/6通過；完整Python測試23/23通過；Node前端測試通過；指定Python檔案`py_compile`通過；Mermaid 11.13.0解析13/13通過；測試涵蓋初始高電位、tick回繞、短暫低／高抖動、穩定低重新武裝與最近5筆歷史。未進行ESP32實機驗證。
- **部署／回復：**更新`tasks.py`；在裝置私人`config.py`同步加入`PIR_POLL_INTERVAL_MS = 100`、`PIR_HIGH_DEBOUNCE_MS = 200`、`PIR_LOW_REARM_MS = 500`、`MOTION_DETECTED_HOLD_MS = 5000`，不可用公開範例覆蓋私人WiFi設定。同步更新時可上傳`config.example.py`僅作公開基線；重啟ESP32後觀察實際PIR，再依硬體輸出調整三個時間參數。回復時還原`tasks.py`與私人設定的新增欄位。

## CHG-20261012-015｜補充PIR冷卻值來源與狀態機改進提案

- **類別：**需求變更（文件澄清）。
- **日期／紀錄時間：**2026-10-12 01:05:19 +08:00，工具取得台北時間。
- **原因：**使用者詢問`5000ms`的來源及是否存在比固定冷卻時間更好的PIR判斷方式；現行文件只描述5秒行為，沒有明確標示它是沿用的啟發式，也沒有區分尚未實作的狀態機提案。
- **作法：**同步更新`WEB_UI_EXECUTION_GUIDE.md`與`SYSTEM_ARCHITECTURE.md`：明確說明5000 ms來自既有`detected`保持時間、不是硬體校正值；補充「穩定高電位確認、觸發一次、穩定低電位重新武裝」狀態機作為改進提案，並標示目前尚未實作。
- **影響：**只修改教學／架構說明，不改變目前ESP32行為；現行程式仍使用`PIR_RETRIGGER_COOLDOWN_MS = 5000`。提案不可當成已部署功能。
- **驗證：**Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過；本次沒有修改程式，因此沿用CHG-20261012-014已記錄的23/23 Python、Node與語法驗證。未進行ESP32實機驗證。
- **部署／回復：**不需重新上傳韌體；同步納入兩份文件與`ChangeLog.md`即可。回復時還原本紀錄涉及的文件段落。

## CHG-20261012-014｜抑制單次移動造成的重複PIR偵測

- **類別：**BUG（一次手靠近被計為兩次移動）。
- **日期／紀錄時間：**2026-10-12 00:56:11 +08:00，工具取得台北時間。
- **原因：**`pir_monitor_task()`只依前一輪的高／低電位判斷低到高邊緣；PIR輸出若在同一次靠近期間短暫低再回高，500 ms輪詢會把抖動視為第二次移動。原本的5秒`detected`顯示保持時間沒有阻止事件計數再次增加。
- **作法：**新增`PIR_RETRIGGER_COOLDOWN_MS = 5000`（同步更新`config.example.py`），`tasks.py`在低到高邊緣觸發前檢查距離上次有效偵測的時間；冷卻期間只更新目前感測狀態，不設定新的`motion_event`、不增加`count`、不加入`recent_detections`。冷卻後的新低到高才視為新事件。
- **影響：**同一次移動造成的短暫低／高抖動不再重複播放音樂或增加網頁移動次數；目前5秒內的第二次真實靠近也會被視為同一事件，需依實機感測器特性調整`PIR_RETRIGGER_COOLDOWN_MS`。預設值與既有5秒顯示保持時間一致。
- **驗證：**PIR／音樂測試6/6通過，新增測試確認冷卻期間的第二個低到高被抑制、冷卻後可重新計數；完整Python測試23/23通過，Node前端測試通過，指定Python檔案`py_compile`通過；Web／系統文件Mermaid 11.13.0解析13/13通過。未進行ESP32實機驗證。
- **部署／回復：**需更新`tasks.py`；建議在裝置私人`config.py`加入`PIR_RETRIGGER_COOLDOWN_MS = 5000`，不可用公開`config.example.py`覆蓋私人WiFi設定；`config.py`未加入版本控制。`index.html`與`web_server.py`本次不因PIR去重而必須更新，除非尚未部署前一版狀態API／網頁修改。回復時還原`tasks.py`與設定範例，並重啟ESP32。

## CHG-20261012-013｜修正閃紅次數為完整警示事件次數

- **類別：**BUG（LED閃紅計數語意不符合需求）。
- **日期／紀錄時間：**2026-10-12 00:44:14 +08:00，工具取得台北時間。
- **原因：**前一版把低光警示內的每一次紅燈閃爍當成一筆紀錄，因此完整閃紅5次會顯示為5次；使用者定義「完整閃紅5次才算閃紅1次」。
- **作法：**`services/led_service.py`改為只有完成整組`LIGHT_ALERT_BLINK_COUNT`次閃紅後才增加`alert_flash_count`，並以整組完成時間建立一筆`alert_flash_log`；未完成的警示不計入。事件序號保留最近5筆，序號仍以裝置開機後完成的事件總數遞增。`index.html`移除`次數／5`顯示，改顯示完成事件總數；`web_server.py`沿用相同欄位名稱但同步新的語意。測試、Web／系統架構文件補充完整事件定義。
- **影響：**例如LED完整閃紅5次後顯示`閃紅次數：1`與`閃紅1：完成時間`；第二次完整警示才顯示`閃紅次數：2`。`alert_flash_total`仍代表一個事件內的閃爍動作數，不是事件次數。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；`python -B -m unittest discover -s tests -v`通過22/22，包含兩個完整警示事件序號驗證；指定Python檔案`py_compile`通過；Chromium以事件級mock確認顯示`閃紅次數：1`與`閃紅1：完成時間`，且uPlot Canvas存在；Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過。未進行ESP32實機驗證。
- **部署／回復：**需同步部署`index.html`、`web_server.py`、`services/led_service.py`、測試與兩份同步文件；不需重新部署RFID／PIR程式。回復時同步還原本紀錄涉及的檔案，避免前端把事件次數誤顯示為單次閃爍次數。

## CHG-20261012-012｜顯示LED閃紅、RFID與移動偵測最近紀錄

- **類別：**需求變更（狀態可觀測性與網頁卡片顯示）。
- **日期／紀錄時間：**2026-10-12 00:26:20 +08:00，工具取得台北時間。
- **原因：**使用者要求LED狀態區顯示閃紅次數及「閃紅序號：時間」，RFID只顯示最近5次「卡號：讀卡時間」，移動偵測只顯示最近5次偵測時間；原本API只保留單筆RFID／PIR摘要，LED也沒有閃紅事件時間。
- **作法：**`services/led_service.py`在每次低光閃紅開始時以裝置時間記錄`alert_flash_log`，snapshot新增`alert_flash_count`、`alert_flash_total`與紀錄清單；`hardware/rfid.py`與`tasks.py`保留最多5筆`recent_reads`；`hardware/motion.py`與`tasks.py`保留最多5筆`recent_detections`；`web_server.py`的LED fallback同步提供新欄位。`index.html`新增LED閃紅次數／時間列表，RFID與移動卡片改以最近5筆資料重繪。兩份架構／Web教學文件補充API欄位、RAM生命週期與畫面對應；測試加入歷史資料與LED時間紀錄驗證。
- **影響：**`/api/data`與`/api/led/status`新增LED閃紅紀錄欄位，RFID／PIR快照新增最近紀錄欄位，不移除既有最後一筆欄位。歷史只存在ESP32 RAM，重啟清空；前端不另行累積。LED閃紅紀錄最多依設定的警示次數保存，RFID與移動偵測固定最多5筆。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；`python -B -m unittest discover -s tests -v`通過22/22；指定Python檔案`py_compile`通過；Chromium以模擬API實際檢查LED顯示5筆序號／時間、RFID只顯示輸入6筆中的最後5筆、移動偵測只顯示輸入6筆中的最後5筆，且uPlot Canvas存在；完整文件13/13個Mermaid區塊以Mermaid 11.13.0解析通過。未進行ESP32實機驗證。
- **部署／回復：**需同步部署`index.html`、`web_server.py`、`services/led_service.py`、`hardware/rfid.py`、`hardware/motion.py`、`tasks.py`及其相依版本文件，重啟ESP32後強制重新整理瀏覽器；不可只上傳`index.html`，因為新欄位由裝置端狀態與API提供。回復時同步還原上述程式、測試、文件與本紀錄，避免前端與API契約不一致。

## CHG-20261012-011｜由/api/data提供光照遲滯門檻

- **類別：**需求變更（API與網頁圖表設定同步）。
- **日期／紀錄時間：**2026-10-12 00:05:15 +08:00，工具取得時間。
- **原因：**確認光照紅線不應在`index.html`重複寫死1000／1100；實際裝置`config.py`的觸發值為500、復位值為1100，前端必須使用同一份裝置設定。
- **作法：**`web_server.py`匯入`config`，讓`/api/data`新增`light_thresholds.trigger`與`light_thresholds.reset`；`index.html`新增`updateLightThresholds()`，從API回應更新uPlot紅線與數字標籤，初次缺少有效欄位時不繪製、已取得有效值後暫時缺欄位則保留最後值。更新Python／Node測試與兩份uPlot整合文件。
- **影響：**`/api/data`回應新增欄位，不移除既有欄位；光照紅線會顯示裝置實際門檻，例如目前`暗 500`／`亮 1100`。不改變80筆歷史、移動平均（仍未加入）、ADC取樣或LED後端控制。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Python桌面回歸測試20/20通過；`py_compile web_server.py`通過；Chromium以模擬API先提供500／1100、再改提供700／1200，確認前端門檻診斷值同步更新且uPlot圖表仍正常；Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過。未進行ESP32實機驗證。
- **部署／回復：**同步部署`web_server.py`與`index.html`，重啟ESP32並強制重新整理；回復時兩者與文件、`ChangeLog.md`需同步還原，避免前端期待不存在的`light_thresholds`欄位。

## CHG-20261011-010｜在光照圖加入亮暗遲滯紅線

- **類別：**需求變更（網頁圖表操作提示）。
- **日期／紀錄時間：**2026-10-11 23:52:01 +08:00，工具取得時間。
- **原因：**使用者希望在光照折線圖中直接看見亮暗控制的緩衝區，並以數字標示兩條邊界。
- **作法：**`index.html`新增`LIGHT_ALERT_TRIGGER_ADC = 1000`與`LIGHT_ALERT_RESET_ADC = 1100`，透過uPlot`hooks.draw`繪製兩條紅色實線，分別標示`暗 1000`與`亮 1100`；1000～1099的遲滯區間不加入移動平均，也不改變原始光照資料與LED後端判斷。
- **影響：**圖表在目前0～2048或高值時0～4095的Y軸內顯示兩條操作參考線；前端門檻常數必須與裝置端`config.py`保持一致。API、80筆歷史視窗、uPlot資產與ESP32控制邏輯不變。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Chromium以本機uPlot資產及模擬API確認0～2048與擴展至4095時，1000／1100兩條紅色實線及標籤都有Canvas紅色像素；未進行ESP32實機驗證。
- **部署／回復：**只需部署更新後的`index.html`；回復時還原本紀錄前的`index.html`、文件與`ChangeLog.md`即可。

## CHG-20261011-009｜光照歷史折線改顯示最近80筆

- **類別：**需求變更（網頁圖表顯示範圍）。
- **日期／紀錄時間：**2026-10-11 23:32:39 +08:00，工具取得時間。
- **原因：**使用者希望利用整列光照卡片顯示較長的光照歷史，先觀察80筆原始資料的折線效果；本次不加入移動平均或其他濾波。
- **作法：**`index.html`將`LIGHT_HISTORY_LIMIT`由20改為80，光照卡片說明文字、`WEB_UI_EXECUTION_GUIDE.md`與`SYSTEM_ARCHITECTURE.md`同步改為最近80筆，X軸滑動視窗同步維持`0～79`；資料仍限制在0～4095並沿用2048／4095自適應Y軸。
- **影響：**以目前約每秒一次的感測輪詢，圖表約涵蓋80秒；歷史仍只存在瀏覽器RAM，`/api/data`、ESP32後端與uPlot資產不變。80筆增加的是觀察時間範圍，不等同數學上的平滑處理。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Chromium以本機uPlot資產及模擬API加入81筆原始樣本，確認保留80筆、X軸為`0～79`、Canvas存在且最後資料仍為原始值，未套用移動平均。未進行ESP32實機驗證。
- **部署／回復：**只需部署更新後的`index.html`；文件同步納入版本庫。回復時還原本紀錄前的`index.html`、`WEB_UI_EXECUTION_GUIDE.md`、`SYSTEM_ARCHITECTURE.md`與`ChangeLog.md`即可。

## CHG-20261011-008｜補充uPlot與Web資產整合教學文件

- **類別：**需求變更（文件補充）。
- **日期／紀錄時間：**2026-10-11 23:24:01 +08:00，工具取得時間。
- **原因：**使用者要求詳細說明uPlot如何整合進`index.html`與`web_server.py`（使用者訊息中的`web_server.ph`依目前專案實際檔名更正為`.py`），讓載入順序、資料生命週期、軸範圍、靜態資產路由、快取與ESP32部署責任清楚可追蹤。
- **作法：**在`WEB_UI_EXECUTION_GUIDE.md`新增uPlot整合專節，說明HTML引用、`updateLightChart()`資料流、20筆瀏覽器歷史、X／Y軸設定、Canvas更新、錯誤定位與`Response.send_file()`路由；在`SYSTEM_ARCHITECTURE.md`新增裝置資料／頁面應用／繪圖函式庫的責任分層、部署檢核與故障邊界。
- **影響：**只修改教學與架構文件，不改變程式、API、部署資產或裝置行為；兩份Markdown的整理時間更新為2026-10-11 23:23:20 +08:00。
- **驗證：**Mermaid 11.13.0實際解析`WEB_UI_EXECUTION_GUIDE.md` 12/12、`SYSTEM_ARCHITECTURE.md` 1/1，共13/13個圖表區塊通過；uPlot URL、路由、函式名稱與部署檔案以目前`index.html`／`web_server.py`實作交叉檢查一致。未進行ESP32實機驗證。
- **部署／回復：**文件可直接納入版本庫；回復時還原本紀錄前的`WEB_UI_EXECUTION_GUIDE.md`、`SYSTEM_ARCHITECTURE.md`與`ChangeLog.md`即可。

## CHG-20261011-007｜修正uPlot光照折線只顯示前兩點

- **類別：**BUG（光照圖表更新）。
- **日期／紀錄時間：**2026-10-11 22:53:23 +08:00，工具取得時間。
- **原因：**使用者回報uPlot折線只顯示前兩點且不再向後延伸。原因是更新資料時保留`setData(..., false)`，但X軸仍使用自動範圍；初始範圍未同步到新增資料，造成後續點落在可視範圍外。
- **作法：**將uPlot X軸改為明確的非自動範圍，依目前最近20筆資料同步設定`0`至`length - 1`（單點時至少保留`0～1`）；Y軸既有自適應2048／4095邏輯不變。測試替身同步記錄X軸範圍，加入點數增加時X軸上限擴展的回歸檢查。
- **影響：**光照折線會隨新資料延伸，超過20筆後保留最近20筆並維持可視寬度；不改變感測資料契約或其他卡片。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Python桌面回歸測試20/20通過；`py_compile web_server.py`通過；Chromium以本機uPlot資產及模擬API加入光照樣本後，確認資料長度達20且X軸範圍為0～19，折線會持續向後延伸。未進行ESP32實機上傳與實機瀏覽器驗證。
- **部署／回復：**部署更新後的`index.html`與`ChangeLog.md`；回復時還原本紀錄前的`index.html`即可。

## CHG-20261011-006｜部署本機uPlot並改用自適應光照圖表

- **類別：**需求變更（網頁圖表與部署資產）。
- **日期／紀錄時間：**2026-10-11 22:27:21 +08:00，工具取得時間。
- **原因：**使用者同意以輕量圖表函式庫取代自製SVG光照圖，並要求光照Y軸聚焦在實際常用的2048以下區間；同時必須把函式庫下載並隨ESP32 Web資源部署，不依賴外部CDN。
- **作法：**固定採用uPlot 1.6.32，從npm官方tarball下載並以npm metadata的SHA-512 integrity驗證通過；部署`assets/uplot/1.6.32/uPlot.iife.min.js`（51081 bytes）、`uPlot.min.css`（1857 bytes）及MIT `LICENSE`。`web_server.py`新增兩個固定資產路由，使用`Response.send_file()`串流與長效快取。`index.html`改以uPlot Canvas繪製最近20筆光照資料；Y軸平時為0～2048並使用0／512／1024／1536／2048刻度，資料出現大於2048時擴展至4095並使用完整刻度，超出ADC邊界的資料限制到0～4095。
- **同步更新：**`tests/test_led_polling.cjs`、`tests/test_rfid_ui.cjs`加入uPlot測試替身與自適應Y軸範圍驗證；`WEB_UI_EXECUTION_GUIDE.md`、`SYSTEM_ARCHITECTURE.md`與`GIT_VERSION_CONTROL.md`補充本機資產生命週期、路由、ESP32部署結構及資產納入版控的指令。
- **影響：**新增約51 KB JavaScript與約2 KB CSS的本機Web資產；不改變`/api/data`、LED快速狀態、LED owner、RFID或移動偵測資料契約。資產版本固定於URL路徑，升級函式庫時需同步新增版本目錄、路由與部署檔案。
- **驗證：**uPlot tarball integrity通過；`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Python桌面回歸測試20/20通過；`py_compile web_server.py`通過；修改後的`WEB_UI_EXECUTION_GUIDE.md`與`SYSTEM_ARCHITECTURE.md`全部13個Mermaid區塊以Mermaid 11.13.0 parser解析通過。Chromium以本機靜態資產及模擬API實際驗證uPlot載入、Canvas建立、0～2048一般刻度、超過2048時4095刻度、折線繪製及窄螢幕布局。未進行ESP32實機上傳、MicroPython資產路由與實機瀏覽器驗證。
- **部署／回復：**上傳`index.html`、`web_server.py`、`assets/uplot/1.6.32/`、測試與文件；重啟ESP32並強制重新整理瀏覽器。回復時需同步移除uPlot資產路由與資產，或還原本紀錄前的`index.html`與`web_server.py`，避免頁面請求不存在的資產。

## CHG-20261011-005｜放大光照折線圖並補充Y軸刻度

- **類別：**需求變更（網頁介面）。
- **日期／紀錄時間：**2026-10-11 21:52:05 +08:00，工具取得時間。
- **原因：**使用者希望光照卡片撐滿整列，並透過Y軸刻度與水平虛線清楚辨識光照數值所在區域及變化。
- **作法：**`index.html`讓光照卡片跨滿感測卡片區整列；SVG圖表擴大為全列寬度，新增固定0～4095 ADC的Y軸刻度（4095、3072、2048、1024、0）與五條水平虛線；折線改依ESP32 12-bit ADC固定範圍繪製，超出範圍的顯示值限制在圖表邊界內。`tests/test_led_polling.cjs`新增0與4095邊界位置驗證。
- **影響：**只改變光照網頁呈現與瀏覽器繪圖座標，不改變光照API、警示閾值、LED owner或其他卡片資料。固定Y軸讓不同時間的圖表可直接比較，但低幅度變化可能比自動縮放更不明顯。
- **驗證：**已執行 `node tests/test_led_polling.cjs`、`node tests/test_rfid_ui.cjs`，兩項均通過；`python -B -m unittest discover -s tests -v` 執行20個測試，20/20通過。以模擬API回應完成Chromium實際檢查：桌面光照卡片跨滿整列、Y軸刻度與水平虛線可見，變化資料可依固定ADC範圍繪製；窄螢幕光照卡片寬度符合單欄布局。未進行ESP32實機驗證。
- **部署／回復：**部署時更新 `index.html` 與前端測試檔；瀏覽器強制重新整理。可回復本次修改前的 `index.html`、`tests/test_led_polling.cjs` 與本紀錄新增段落。

## CHG-20261011-004｜重新配置網頁儀表板卡片與光照折線圖

- **類別：**需求變更（網頁介面）。
- **日期／紀錄時間：**2026-10-11 21:39:33 +08:00，工具取得時間。
- **原因：**使用者要求將光照卡片改為折線顯示，RFID 與移動偵測卡片並列，將 LED 狀態區移到控制按鈕上方，並放大主要文字。
- **作法：**`index.html`新增不依賴外部套件的 SVG 光照折線圖，保留最近 20 次有效 ADC 讀值並由既有感測輪詢更新；RFID／移動偵測改用雙欄卡片布局，窄螢幕自動改為單欄；LED 狀態與命令提示合併成狀態區並移到按鈕列上方；同步放大卡片、系統狀態、LED 狀態與按鈕文字。`tests/test_led_polling.cjs`及`tests/test_rfid_ui.cjs`補充折線圖更新與空圖提示驗證。
- **影響：**只改變網頁呈現與瀏覽器內的光照歷史快取，不改變後端 API、LED 權限／busy 檢查、RFID／PIR資料契約或 ESP32 控制流程。光照折線歷史於頁面重新載入後清空。
- **驗證：**已執行 `node tests/test_led_polling.cjs`、`node tests/test_rfid_ui.cjs`，兩項均通過；`python -B -m unittest discover -s tests -v` 執行 20 個測試，20/20 通過。以本機靜態頁面及模擬 API 回應完成 Chromium 實際布局檢查：桌面 RFID／移動偵測同列、LED 狀態在按鈕上方、光照折線圖可見；窄螢幕兩卡片改為單欄。未進行 ESP32 實機驗證。
- **部署／回復：**部署時更新 `index.html`，瀏覽器強制重新整理以取得新頁面；可由本次修改前的 `index.html` 與兩個測試檔案回復，後端不需重新上傳。

## CHG-20261011-003｜補充新增LED效果需求的快速整合方法

- **類別：**需求變更（文件）。
- **日期／紀錄時間：**2026-10-11 16:51:48 +08:00，工具取得時間。
- **原因：**使用者要求將「增加按鈕 3、按下時綠閃 3 次」的擴充說明整合進單一 LED owner 講義，說明目前機制如何在不新增第二個控制者的情況下快速加入新需求。
- **作法：**`LED_SINGLE_OWNER_GUIDE.md` 新增 0.8 節，說明綠閃效果規格、紅閃／綠閃同時發生時採先接受者完成、後來者以 `busy` 拒絕的政策；補充正常／效果狀態流程、按鈕去彈跳與按住拒絕、`main.py`／`tasks.py`／`config.example.py`／`services/led_service.py`／測試的整合點，以及新增效果所需的測試清單。
- **已實作／提案：**本次只更新文件，沒有新增按鈕 3、綠閃效果或任何韌體程式；`_EFFECTS` 表與相關程式片段是後續實作建議，不代表目前程式已支援綠閃。
- **驗證：**既有文件的 21 個 Mermaid 區塊使用 Mermaid 11.13.0 parser 實際解析，21/21 通過；桌面回歸測試執行 20 個測試，20/20 通過。未進行新增按鈕 3 的 ESP32 實機驗證，因本次未修改程式。
- **影響／部署／回復：**只更新教學文件與變更紀錄，不需重新上傳韌體。可由本次修改前的 Git 版本回復 `LED_SINGLE_OWNER_GUIDE.md`；既有 LED 控制機制不變。

## CHG-20261011-002｜以國中生比喻與第一性原理重整LED單一擁有者講義

- **類別：**需求變更（文件與教學順序）。
- **日期／紀錄時間：**2026-10-11 15:33:16 +08:00，工具取得時間。
- **原因：**使用者要求先清楚說明三種需求共用一個三色 LED 所造成的紅閃、恢復、禁用與時序錯亂，再說明目前解法；並以費曼式、國中生可理解的比喻建立第一性原理技術樹，明確區分目前實機操作良好與尚未完整測試。
- **作法：**重整 `LED_SINGLE_OWNER_GUIDE.md` 開頭閱讀路線，新增「問題→解法→第一性原理技術樹→技術點逐一解釋→證據界線」；用受理窗口、待辦清單、LED 工作員、號碼牌、火警演習與公告欄等比喻對應 `submit`、`queue`、`LedService.run`、receipt、reserved／busy、狀態機、快照與後端權威；保留後續案例、網頁狀態、附錄規格與部署參考。
- **已實作／提案：**本次只修改講義，不修改 LED 控制程式；目前架構仍是實體按鈕、網頁按鈕與光感警示共用單一 LED owner。更好的仲裁機制仍是後續比較題目；MQTT callback 未接通與實機測試不完整的限制已在講義中明確標示。
- **驗證：**`LED_SINGLE_OWNER_GUIDE.md` 全部 21 個 Mermaid 區塊使用 Mermaid 11.13.0 parser 實際解析，21/21 通過；`python -B -m unittest discover -s tests -v` 執行 20 個桌面回歸測試，20/20 通過。未宣稱已完成 ESP32 實機、長時間、多來源壓力、網路或所有故障時序驗證。
- **影響／部署／回復：**只更新教學文件與變更紀錄，不需重新上傳韌體。可由本次修改前的 Git 版本回復 `LED_SINGLE_OWNER_GUIDE.md`；既有 `CHG-20261011-001` 與歷史紀錄保留。

## CHG-20261011-001｜從 main.py 重整 ESP32 系統架構文件

- **類別：**需求變更（文件）。
- **日期／紀錄時間：**2026-10-11 14:32:36 +08:00，工具取得時間。
- **原因：**使用者要求從 `main.py` 開始解析 ESP32 IoT 專案，並將分析整合回 `SYSTEM_ARCHITECTURE.md`；原文件仍含九個任務、LED 直接寫入、RFID／PIR／喇叭未整合等過時描述。
- **作法：**重整 `SYSTEM_ARCHITECTURE.md`，補充 `boot.py`→`main.py` 啟動鏈、硬體初始化順序、共享事件與狀態、目前 13 個應用協程、`LedService` 單一 owner、DHT／光感／PIR／RFID／OLED／喇叭資料流、HTTP API、MQTT callback 未接通的實作限制、部署相依與實機檢核順序。同步移除已不符合目前程式的舊 LED `off()`／自動控制描述。
- **已實作／提案：**本次只更新文件；文件中的 MQTT 修正、感測資料品質、健康監控、任務 supervisor、安全與部署改善仍是待後續實作的提案，未宣稱已修正程式。
- **驗證：**`SYSTEM_ARCHITECTURE.md` 的全部 1 個 Mermaid 區塊已使用 Mermaid 11.13.0 parser 實際解析，1/1 通過；`python -B -m unittest discover -s tests -v` 執行 20 個桌面回歸測試，20/20 通過。未進行 ESP32 實機、GPIO 接線、WiFi、MQTT、Microdot 或周邊驗證。
- **影響／部署／回復：**只需更新教學文件，不需重新上傳韌體。可由本次修改前的 Git 版本回復 `SYSTEM_ARCHITECTURE.md`；`ChangeLog.md` 保留本紀錄與既有歷史。


## CHG-20261007-006｜實測後補充狀態有效期限講義

- **類別：**需求變更（講義與後續協作規則）。
- **日期／紀錄時間：**2026-10-07 14:35:19 +08:00，工具取得時間。
- **原因與實測來源：**使用者回報瀏覽器重新整理後不再因連線失敗訊息讓按鈕1瞬間失能，依先前約定補入講義。精確實測時間、持續時間與HTTP數據未提供；不宣稱偶發查詢失敗根因已修正。
- **作法：**LED_SINGLE_OWNER_GUIDE.md新增8C，以比較表、角色／變數表、決策圖、時序案例說明內容相同仍重新確認、連線健康與LED有效性分離、5秒期限、200ms監視、1秒timeout、診斷RAM與部署快取。8A前加版本提示，標示單次失敗立即停用已被取代；AGENTS.md優先規則同步引用8C及期限原則。
- **已實作／提案：**程式沿用5f3807c，不修改程式或參數；5秒是目前值並非普遍安全保證。PIR輸出仍沿用ab5465f，尚無新實機確認。本次沒有新增推送或事件歷史。
- **驗證：**講義全部20張Mermaid圖已使用11.13.0實際解析，20/20通過；未Typora／VS Code視覺布局驗證。純文件／規則修改不重跑程式測試，桌面結果與使用者實機回報分開記錄。
- **影響／部署／回復：**無需重新上傳ESP32；只更新教學與後續設計規則。ab5465f保存文件修改前版本，留在refactor/led-single-owner本機提交，未推送或合併。

## CHG-20261007-005｜PIR終端輸出改為帶時間的移動事件

- **類別：**需求變更。
- **日期／紀錄時間：**2026-10-07 14:25:22 +08:00，工具取得時間。
- **原因：**使用者希望Thonny不再被GPIO讀值0洗版，移動時顯示偵測時間。
- **作法：**tasks.py移除GPIO變化／每20次輪詢的診斷輸出與其計數器；首次高電位或低轉高時輸出偵測日期時間，沿用get_current_time，與網頁last_detected_at共用該次時間。持續高電位不重複輸出。啟動與錯誤訊息保留，偵測、音樂與網頁狀態政策不變。
- **驗證：**4個PIR／音樂桌面回歸測試通過；未ESP32／Thonny實機驗證。時間依裝置現有時鐘，未同步NTP時不保證實際時間準確。
- **部署／回復：**上傳tasks.py後重啟；5f3807c保存修改前版本。同步維護無狀態參數的測試時間來源，未修改講義；本機提交，未推送。

## CHG-20261007-004｜短暫LED查詢失敗與連線健康分開判斷（待實機確認）

- **類別：**BUG。
- **日期／內容紀錄時間：**2026-10-07 14:21:02 +08:00，工具取得時間。
- **原因：**使用者確認無操作時仍常見「LED狀態回應逾時或連接失敗」瞬閃；光照持續有資料。前端單次查詢失敗立即停用、下一次成功立即恢復，造成操作混淆。頻繁失敗根因尚未量測，不能宣稱網路或排程問題已修復。
- **比較基線：**修改前工作目錄乾淨，既有commit f6b8e53已保存立即停用版本，無需建立空提交；本次可用git diff f6b8e53比較。
- **作法：**index.html以performance.now單調時間分開記錄最近LED成功確認與任一資料API成功時間；LED內容即使相同也更新確認時間。單次失敗保留原狀態，LED超過5秒未確認才停用；光照API成功只能確認連線，不延長LED有效期限或回寫LED副本。獨立200ms監視有效期限，不必等HTTP回應才發現過期。紅閃／服務不可用仍立即停用，後端busy檢查不變。
- **參數與診斷：**5秒為待實測的容忍值，1秒單筆timeout及200ms輪詢保留；getLedDiagnostics提供连续失敗數、最近錯誤與兩種資料年齡，成功清除連續失敗數但保留最近錯誤。只存一筆錯誤與快照，不累積歷史。未取得新狀態時可能暫時保留過去可操作提示，後端仍拒絕紅閃改色。
- **驗證：**2組桌面JavaScript測試及20個Python回歸測試通過，涵蓋單次失敗不閃動、感測成功不延長LED期限、整體連線過期、相同快照刷新期限、晚到回應忽略與原RFID／PIR功能。未實機測試，講義依使用者要求待確認後再更新。
- **部署／回復：**僅需上傳index.html並強制重新整理，沿用已部署快速狀態API。可由f6b8e53取得舊index.html回復比較。只在本機分支實作／提交，未推送或合併。

## CHG-20261007-003｜講義比較網頁狀態架構並建立優先設計規則

- **類別：**需求變更（講義與協作規則）。
- **日期／內容紀錄時間：**2026-10-07 13:28:35 +08:00，工具取得當前時間。
- **原因：**使用者確認更新後即時反應良好，要求說明前後架構、改良思路與舊設計缺點，並優先沿用此方式。實機測試精確時間與量測數據未提供，不宣稱200ms上限或所有情況穩定。
- **作法：**LED_SINGLE_OWNER_GUIDE.md新增8B，包含雙架構圖、比較表、取樣／HTTP等待、重疊與舊回應風險、完整紅閃案例、RAM／JSON／Promise生命週期、逾時與權威控制、適用前提及流量／短事件限制。AGENTS.md增加網頁狀態顯示規則，優先輕量快照分流、單筆在途與逾時處理；200ms不作為通用固定值。
- **已實作與提案：**程式沿用2d62a2c，這次只修改文件／規則；事件紀錄、SSE／WebSocket僅說明替代方案，未實作。未以推論取代實測，舊回應亂序是程式風險而非已證實實機根因。
- **驗證：**講義全部18張Mermaid圖已使用11.13.0實際解析，18/18通過；未做Typora／VS Code視覺布局驗證。純文件修改，不重跑程式測試；先前20個Python與2組JavaScript測試結果見前次紀錄，實機反應良好由使用者本次回報。
- **影響／部署／回復：**不需上傳ESP32；講義與後續協作設計優先規則改變。以2d62a2c可取得本次文件修改前版本。留在refactor/led-single-owner本機提交，未合併或推送GitHub。

## CHG-20261007-002｜LED網頁狀態獨立快速輪詢，避免舊感測回應覆蓋

- **類別：**BUG。
- **日期／開始時間：**2026-10-07 13:01:16 +08:00。
- **桌面測試／內容紀錄時間：**2026-10-07 13:04:21 +08:00。
- **現象：**使用者回報實機紅閃開始約2秒後網頁才顯示警示／disable按鈕1，因效果已結束，提示瞬閃又恢復可操作。未取得HTTP時間線或ESP32排程量測，不能確認所有延遲來源。
- **確認的程式風險：**LED提示綁每秒/api/data；該端點包含感測資料處理，前端setInterval可使多筆請求重疊。較舊回應可能在較新回應之後更新LED。這不表示owner的busy檢查失效，提示與實際控制權應區分。
- **作法：**新增/api/led/status，只複製LedService RAM快照、不操作ADC／DHT／SPI／GPIO，回no-store。前端LED獨立完成後等200ms輪詢，單筆在途Promise共用；感測完成後等1000ms再取並防重疊，不再由感測回應更新LED或因感測失敗覆蓋LED通道。切色後亦刷新快速LED狀態。
- **逾時／資料生命週期：**LED請求1秒未完成用AbortController中止，顯示未知並停用；Promise.race忽略逾時後晚到回應，成功新快照才恢復。在途請求結束釋放Promise與timer；不持續累積setInterval請求。不變更命令佇列、owner仲裁或實體按鈕規則。
- **驗證：**20個Python測試通過，Microdot實際路由驗證新端點不調用ADC與no-store；原網頁JavaScript測試與新增延遲fetch測試通過，涵蓋慢感測不擋警示、舊感測不重新啟用、單筆在途、Abort逾時、晚到忽略與恢复。未實機重測、瀏覽器布局或HTTP延遲量測。講義新增通道圖，全部17張Mermaid圖已使用11.13.0實際解析，17/17通過。
- **影響與限制：**正常情況LED輪詢更密集、每頁最多約5次每秒，仍有HTTP與事件迴圈延遲，不保證200ms內更新。同步阻塞、WiFi或背景節流仍可能延遲，不能宣稱2秒根因完全解決；後端拒絕政策保持權威，未知狀態不放行。
- **文件／部署／回復：**LED_SINGLE_OWNER_GUIDE.md新增案例8A分流機制；更新web_server.py、index.html後重啟並強制刷新瀏覽器。不需更改config.py。回復4778911可取得原前端／API，須成對部署。本次留在refactor/led-single-owner本地提交，未推送。

## CHG-20261007-001｜以案例與分層圖解深化單一 owner 講義

- **類別：**需求變更（教學內容深化）。
- **日期／開始時間：**2026-10-07 02:57:54 +08:00。
- **內容紀錄時間：**2026-10-07 03:02:08 +08:00；16張Mermaid圖已於提交前確認解析通過。
- **需求與驗證來源：**使用者回報目前實機測試情況良好，要求降低認知負荷，詳細說明要素、邏輯與實際情境。實機時間、逐項測試與壓力數據未提供，不推論所有情境已驗證；本次沒有程式變更。
- **教學順序：**LED_SINGLE_OWNER_GUIDE.md 改成角色→資料→初始化→案例→進階附錄，前半先教提出要求、受理窗口、待辦清單、唯一工作者與GPIO工具，再對應實際函式。原完整規格保留於附錄供查表，不要求初次一次理解全部欄位。
- **資料機制：**分清命令、正常狀態、effect、receipt與實際GPIO；說明submit在來源task執行，run在唯一owner task執行，但共用同一LedService物件。queue與results引用同一receipt，來源拿副本，結果查詢再複製；queue移除不會立即刪掉結果，最近16筆之外才過期。
- **新增案例：**實體按鈕按下、ADC900觸發、兩事件接近同時、紅閃第三次期間按下並按住、網頁刷新前誤送POST、閃完後1100解除。各主案例有初始假設、Mermaid時序圖、函式／參數與資料位置、狀態表、最終結果及自我檢查。
- **競爭情境分解：**按鈕已執行則警示保存新綠色；按鈕已受理仍排隊則警示受理把它標rejected/alert_started，恢復舊藍色；警示先受理則按下被消耗或submit回busy。強調accepted不等於executed，不把感覺同時誤當同時執行，也不把所有拒絕路徑都說成產生命令ID。
- **保留課堂易錯點：**busy=false不等於armed=true；首次受理時busy已生效但effect可能仍None；持續按住不會在警示後補執行；必须警示後取樣ADC>=1100再ADC<1000。約20ms是檢查節奏、300ms是亮滅階段，不把理想時間表誤當精準實機量測。
- **驗證範圍：**逐項对照現有LedService、Button、tasks、main與Web程式。講義共有16張Mermaid圖，已使用11.13.0實際解析全部區塊，16/16通過。未做Typora／VS Code視覺布局驗證。純文件修改，不重跑程式測試；先前20個桌面測試及使用者實機回報仍按來源區分。
- **部署／回復：**無需重新上傳ESP32。留在refactor/led-single-owner本地提交，未合併或推送；原講義可由da7f007取得比較。先前卡鈍觀察不在此次處理範圍，沒有宣稱修正。

## CHG-20261006-012｜單一 LED owner 與命令仲裁實驗

- **類別：**需求變更（架構教學與獨立分支實驗）。
- **日期／開始時間：**2026-10-06 23:32:51 +08:00。
- **驗證／紀錄時間：**2026-10-06 23:46:02 +08:00。
- **需求：**使用者要求把多元控制單一LED方案寫成講義與Mermaid圖，再切分支實作，評估理解、實作與功能穩定性。不是處理卡鈍；先前卡鈍仍待觀測。
- **基線與狀態：**由乾淨main的88ca2fb建立refactor/led-single-owner；只本地實驗、未合併／推送。73d693f與light-led-alert-validated-20261006仍可回復已確認功能。

### 討論結論與實作

1. **責任集中：**新增services/led_service.py與套件__init__.py。RgbLed改為只轉色碼到GPIO且避免重複輸出；初始化安全熄燈後，正常操作与關機輸出都由唯一LedService.run流程執行。main只建立owner與提出停止，不直接寫GPIO。
2. **生產者：**實體按鈕與Web提交cycle，光照提交low_light_alert；既有MQTT改色分支亦提交set_color以避免留下旁路，但不修改既有MQTT callback接線，也未broker實機驗證。來源不讀改寫正常色碼，不執行效果。
3. **仲裁：**同步submit只做受理控制面，無await／GPIO；普通命令FIFO上限8。受理警示即reserved=true，將尚未執行的普通receipt改rejected/alert_started並清除，避免警示後補執行；忙碌時新改色與新警示立即拒絕、不排隊。cycle是相對變更，兩次不合併。警示先於待執行改色，已執行命令不撤銷。
4. **雙層狀態：**正常色碼／亮滅與effect分開；effect保存phase、次數、階段時間、原狀與receipt。owner每20ms讓出排程，每輪最多4筆，使用ticks_diff推進亮滅。延遲時每輪最多一個效果轉換，不跳過肉眼可見階段，可能延長總時間。五次完成先恢復GPIO，再解除busy並標executed。
5. **結果與生命週期：**receipt有id、kind、source、status、reason；受理副本不會自動變完成，最近16筆結果保留RAM可查，重啟清空。accepted→executing→executed；亦可能rejected、failed、cancelled。記錄可過期，查不到不等於未執行。有界清單不依賴uasyncio.Queue套件，不可從IRQ／thread直接使用。
6. **Web：**POST既有/api/led/toggle回202與ID表示受理，而非已改色；busy409、queue_full429、停止／未初始化503。新增GET /api/led/commands/<int:command_id>；前端區分受理、執行、後續拒絕、過期与斷線未知，不等待警示完成才回HTTP。每秒狀態快照仍顯示警示忙碌並停用按鈕。
7. **停止與錯誤：**request_stop停止受理／拒絕待處理；owner finally標未完效果cancelled、熄燈並set stopped Event。main等待owner完成清理。GPIO錯誤標failed並退出；硬體若連熄燈也失敗，不能承諾實際輸出。只有同一迴圈、經命令入口的來源才符合此所有權約定。
8. **保持功能政策：**完整五次期間拒絕改色、按鈕須放開重按；光照armed仍需警示結束後ADC>=1100才重新允許，再ADC<1000才觸發，未加冷卻或連續確認。未採背景改色／通用搶占，維持先前確認需求。

### 講義、理解成本與替代方案

- 新增LED_SINGLE_OWNER_GUIDE.md，以四張圖表示要素、HTTP受理到結果、警示競爭時機與狀態機，說明參數來源、快取生命週期、仲裁表、部署與驗收。旧LIGHT_LED_ALERT_GUIDE.md加版本提示，保留token方案供比較。
- 講義說明critical section、一致性、所有權、仲裁是互補層次；非同步for+await不阻塞整個迴圈也可取消，本次選狀態機是集中仲裁，不是將其誤當無法中斷。
- 可讀性初步判斷：硬體與來源更簡單、責任集中；owner增加有界佇列、狀態機與結果協定，整體不一定更短，初學者需理解accepted不等於executed。是否更容易教學或實機更穩定仍需驗收，未宣稱結論已成立。
- 未選等待式Lock（會延後操作）、背景desired更新（會不恢復原狀）與泛用優先權搶占框架（目前規則不需要）；單一owner本身不能替代仲裁政策。

### 驗證與可觀察差異

- **20個Python測試通過：**FIFO、兩次cycle、預約警示競爭、拒絕待執行／新命令、完整五次／熄滅恢復、tick回繞、延遲不跳階段、容量／歷史上限、取消／關機、GPIO錯誤、實際main錯誤後owner清理、真正Button去彈跳拒絕與PIR／RFID回歸。固定隨機種子1000輪混合命令加200輪收尾驗證有界與結束。以本專案Microdot TestClient驗證實際路由202、結果查詢與429，另驗證handler409／404。
- **網頁JavaScript模擬測試通過：**受理／執行、受理後拒絕、busy停用、重啟可用以及原RFID／PIR顯示。未真實瀏覽器布局、ESP32 SPI/GPIO、broker或實機壓力驗證。
- **Mermaid：**原暫存解析器依賴缺損，另在暫存目錄建立mermaid11.13.0+jsdom，四張圖實際解析4/4通過；未做Typora／VS Code視覺布局驗證，不增加專案執行依賴。
- **差異：**白色7改由owner於完整初始化後首次渲染，WiFi／NTP／MQTT等待期間LED保持安全熄滅；Web受理成功從200改202；正常命令至少等待owner下一輪，不再同步完成。這些需納入實機驗收。

### 部署與回復

部署main.py、tasks.py、web_server.py、index.html、hardware/led.py與services整個目錄，保留已確認Button、PIR／RFID／sensors及私人config.py。本次未新增配置，既有LIGHT_ALERT_*沿用。重啟重新載入HTML。詳見新講義。

實驗不推送或合併。回復git switch main後須整套部署main/tasks/web_server/index與hardware/led，不可混用舊token控制器和新owner介面；私人配置未改。旧services可留在裝置，但舊main不匯入。每次提交包含此紀錄，實際commit由Git查詢。

## CHG-20261006-011｜講義強調光照警示的重新允許条件

- **類別：**需求變更（教學說明補充）。
- **日期／紀錄時間：**2026-10-06 15:48:55 +08:00。
- **原因：**使用者在教室誤以為紅閃功能失效，後確認是未考慮「先回升至1100或以上，再降到1000以下」的重新允許條件，要求講義強調，避免學生誤解。此項不代表版本BUG或已確認的卡鈍根因。
- **作法：**LIGHT_LED_ALERT_GUIDE.md 在操作規則開頭增加醒目提示、四步實驗流程、五組ADC序列比較與邊界值說明。清楚區分「紅閃結束」和「armed重新允許」，說明遲滯機制、警示期間變亮不算重新允許、教室環境可能達不到解除閾值。
- **機制：**觸發要求ADC<1000且armed；觸發後armed=false。警示結束後背景取樣到ADC>=1100才armed=true；接著低於1000才再觸發。1100可解除，1000不能觸發；一秒保持只是課堂觀察建議，不是程式計時要求。
- **影響／驗證：**僅改講義與本紀錄，按現有tasks.py邏輯核對例子；無程式或配置變更，不重跑測試。修改文件沒有Mermaid圖。先前偶有卡鈍仍待觀測，本次不處理或宣稱已解決。
- **部署／回復：**不需上傳ESP32或重新部署；講義使用新版即可。此文件修改保存本地提交，未另推送GitHub；可透過Git歷史取回旧文件。

## CHG-20261006-010｜保存紅閃確認版並記錄待觀測卡鈍

- **類別：**需求變更（版本發布）；另記錄疑似 BUG，尚未確定或修正。
- **日期／紀錄時間：**2026-10-06 10:26:24 +08:00；實機測試精確時間未提供。
- **需求：**使用者確認紅閃五次相關功能與觸發時機測試正確，要求先合併推送 GitHub。
- **已確認與待觀測的區分：**紅閃結果由使用者實機回報；同時回報移動偵測與實體按鈕偶有卡鈍感受，但尚未詳細觀測。沒有量測、日誌或可重現步驟，未確認根因或與警示的關聯，未修正；依使用者要求後續再調查，不宣稱全系統即時性／效能已通過驗證。
- **作法：**fetch 確認遠端 main 無新增提交；更新 LIGHT_LED_ALERT_GUIDE.md 的驗證範圍與待觀測事項，提交後將 feature/light-led-alert 快轉合併 main，建立帶註解標籤 light-led-alert-validated-20261006，推送 main、功能分支與標籤至原 origin，核對遠端 SHA。
- **驗證與影響：**既有17個Python桌面測試通過，前次網頁JavaScript測試通過；本次無程式邏輯變更，不重複執行。保留五次警示、忙碌拒絕／不排隊、恢復原狀與舊配置相容修正，私人config.py不推送，討論及替代方案仍保留於CHG-20261006-008。
- **部署／回復：**依LIGHT_LED_ALERT_GUIDE.md部署；標籤light-led-alert-validated-20261006保存此次版本，前一版pir-music-web-validated-20261006保留供回復／比較。乾淨工作目錄建立回復分支後重新部署到ESP32，私人配置需另保留；回復舊sensors時恢復舊閾值參數。Git refs 為推送結果依據。

## CHG-20261006-009｜修正舊裝置配置導致感測器匯入失敗

- **類別：**BUG。
- **日期／開始紀錄時間：**2026-10-06 10:05:08 +08:00。
- **現象／原因：**使用者回報 hardware/sensors.py 載入 LightSensor 時缺少 LIGHT_ALERT_TRIGGER_ADC。方法預設參數直接引用 config 屬性，會在定義類別時求值；裝置尚未新增參數或使用舊配置，就在 main 初始化前發生 AttributeError。光照任務的 getattr 預設值無法補救更早的類別匯入錯誤。
- **作法：**is_dark/is_bright 的預設 threshold 改為 None，在實際呼叫時才用 getattr 讀配置，缺少鍵時分別使用 1000／1100；顯式 threshold 仍優先，保留原本 <／> 判斷。未改私人 WiFi 或警示控制規則。
- **驗證：**新增實際載入 sensors 模組的舊配置回歸測試，覆蓋缺少新鍵仍可匯入、預設閾值、顯式參數與動態配置；本次17個Python測試全部通過。桌面 fake ADC，不是 ESP32 實機驗證。
- **部署／回復：**重新上傳 hardware/sensors.py 後重啟；仍建議同步更新裝置 config.py 的 LIGHT_ALERT_*，確保自訂閾值生效，保留私人 WiFi。若撤回此修正，必須先補齊新參數才能避免相同匯入錯誤。本次本地 feature/light-led-alert 提交，未合併或推送。

## CHG-20261006-008｜光照紅閃五次與 LED 操作完整性

- **類別：**需求變更。
- **日期／開始時間：**2026-10-06 09:51:01 +08:00。
- **測試與文件紀錄時間：**2026-10-06 09:59:16 +08:00。
- **實作狀態：**本地 feature/light-led-alert 分支；桌面測試通過，尚未 ESP32 實機確認、合併或推送。

### 需求、討論與最終決策

使用者要求 ADC 低於閾值時先保存 RGB LED 狀態、紅閃五次後恢復，並要求先討論同時控制與分支策略。最初提案將正常狀態與警示輸出分離：警示占用輸出，按鈕更新背景選擇，完成後顯示最新選擇。這種覆蓋機制其實可以避免綠燈插入紅閃，但使用者看不到按下的立即效果，而且完成後不再嚴格恢復原狀。

使用者提出「紅燈閃了三次突然變綠，再閃兩次」會混淆，詢問五次警示是否應為 atomic operation。經討論後，使用者明確同意「警示期間拒絕改色、不排隊、完成後恢復原狀」，並要求本檔記錄討論、實作機制及替代方案優劣。上述背景更新方案未採用。

最終行為：低於 1000 觸發一次，红亮／全滅各 300 ms，五次後恢復 `(色碼, 亮滅狀態)`。警示期間拒絕實體按鈕1、網頁按鈕1與 MQTT 改色；實體按鈕必須放開再重新按下。持續暗不重複，警示完成後取樣到 ADC >= 1100 才重新允許下一次低於 1000 的觸發。開機已暗亦警示一次。系統清理可中止警示並熄燈。

### 如何實現 atomic 行為與資源控制

1. **單一控制入口：**hardware/led.py 的一般方法 set_color_by_index、next_color、on、off、toggle 都經過 `_require_available()`。警示中丟出 LedBusyError，立即拒絕，不等待鎖、不存待執行改色命令。不是只靠網頁停用。
2. **在通知前取得控制權：**light_sensor_task 在觸發時同步 begin_alert，保存 current_color_index 與 is_on，建立唯一 object token，再 Event.set；這段沒有 await，因此一般協程無法在檢查與取得控制權之間插入。警示任務尚未取得排程，入口也已 busy。
3. **取樣與閃爍分離：**main 建立獨立 light_alert_event，將光照取樣與警示任務加入 gather。取樣保持50 ms；警示任務 wait/clear 後取 token，紅亮／熄滅各 await 300 ms。RFID、PIR音樂、按鈕、Web、MQTT仍可取得排程。
4. **不污染正常狀態：**alert_step 只寫 GPIO，紅色為索引4，全滅為0，不改正常色碼／is_on。五次正常完成、普通例外或取消都由 finally/end_alert 恢復快照後才釋放 token。原本關燈時恢復熄滅並保留原選定色碼。
5. **關機優先：**main 使用 shutdown，使 token 失效、清除快照並永久熄燈。晚到的警示步驟或 finally 先檢查 token，不再恢復舊顏色。不是讓一般 off 繞過警示封鎖。
6. **實體輸入消耗：**Button.wait_press 新增 reject_if，最初讀到按下與去彈跳期間記住 press_rejected；即使警示在去彈跳途中結束，仍拒絕該次按下。button1_task 保留 wait_release，不因警示完成後仍按住而補執行。控制器的最終檢查仍封鎖警示於呼叫前開始的競爭情況。
7. **Web／MQTT回應：**/api/data 加入 led.alert_active、available、正常色碼與is_on，網頁每秒刷新停用LED按鈕並提示警示中。POST直接呼叫控制器，忙碌回HTTP409，即使舊頁面、刷新延遲或其他客戶端亦無法繞過。MQTT改色分支捕捉同一錯誤並記錄未執行、不排隊；未做broker端到端測試。
8. **遲滯與RAM：**armed只在警示結束後且讀到解除閾值才重設；警示中亮暗交替不排隊。快照、token、Event、armed都在RAM，重啟清空，不寫Flash。配置同步至私人config.py與公開config.example.py，不修改WiFi秘密。

這裡的 atomic 是應用層排他控制與可見操作完整性，不是三秒內禁止排程，也不是硬體三個GPIO同時切換。保證前提為所有一般LED操作經同一物件、單一uasyncio迴圈、同步檢查／寫入無await；新增執行緒、IRQ或直接寫GPIO需另設同步。取消、例外與關機允許中止五次序列，不能宣稱故障時也必定完成五次。

### 替代方案與優劣（以下未採用者皆僅提案）

| 方案 | 優點 | 缺點／決策 |
|---|---|---|
| 忙碌立即拒絕、不排隊 | 警示完整、恢復原狀、記憶體小、操作結果明確 | 約3秒不能改色，需提示；本次實作 |
| 紅閃覆蓋＋保存最新使用者意圖 | 不插入綠燈，也不丟掉最後選擇 | 按下無即時反應，完成後不恢復原狀；討論後否決 |
| FIFO排隊改色 | 每個命令都可稍後執行 | 延遲後突然連續換色，需上限／過期／回應設計；否決 |
| await互斥鎖 | 可協調共用資源 | 會等待並延後執行，違反不排隊；鎖本身不決定UX／優先權；否決 |
| 手動操作優先並中止紅閃 | 立即反應 | 五次警示可能不完整，需取消與恢復政策；否決 |
| 不協調直接写GPIO | 程式最少 | 紅／綠交錯、狀態恢復競爭，不符合需求；否決 |
| 單一LED工作任務＋命令佇列 | 可擴充多種效果／優先權 | 改造較大，仍需設計忙碌拒絕、佇列與取消；未實作，未來效果增加可考慮 |

### 影響、驗證與部署／回復

- **配置變更：**移除旧 LIGHT_AUTO_CONTROL_ENABLED 與 LIGHT_THRESHOLD_ON/OFF，用 LIGHT_ALERT_ENABLED、LIGHT_ALERT_TRIGGER_ADC、LIGHT_ALERT_RESET_ADC、LIGHT_ALERT_BLINK_COUNT、LIGHT_ALERT_ON_MS、LIGHT_ALERT_OFF_MS 取代自動亮滅模式；sensors輔助方法同步新閾值。保留 LIGHT_POLL_INTERVAL_MS=50。
- **測試：**16個Python測試與網頁JavaScript模擬測試通過，涵蓋五次輸出序列、亮／滅快照恢復、所有一般方法拒絕、去彈跳期間拒絕、實體按下消耗、HTTP409、防止排隊、閾值邊界／遲滯、取消清理與shutdown阻止晚到恢復；LED／RFID／PIR回歸通過。網頁驗證停用、409競爭時機、恢復可用及斷線。未ESP32實機、實際時序、broker或瀏覽器布局驗證。
- **限制：**ADC閾值仍需實際校準；原LightSensor讀取失敗可能返回上次值，未新增量測健康判斷；網頁停用通常有約一秒延遲，後端拒絕才是權威。若對GPIO直接寫值或硬體故障，軟體閘門不能保證輸出。
- **文件／部署：**LIGHT_LED_ALERT_GUIDE.md 詳述機制與替代方案。上傳main、tasks、web_server、index.html及hardware/led、button、sensors，更新装置私人config.py的新參數後重啟刷新，勿以公開範本覆蓋WiFi。
- **版本回復：**保留 pir-music-web-validated-20261006 基線，乾淨工作目錄建立回復分支再部署。Git不恢復私人config.py；回到舊版sensors時須一併恢復該版LIGHT_THRESHOLD_ON/OFF與LIGHT_AUTO_CONTROL_ENABLED=False，WiFi秘密另保留。本次提交本地功能分支，待使用者實機确认才合併／推送。

## CHG-20261006-007｜發布使用者確認正常的 PIR 音樂與網頁版本

- **類別：**需求變更（版本發布與驗證紀錄）。
- **日期／紀錄時間：**2026-10-06 08:56:09 +08:00；使用者實際測試時間未提供。
- **原因：**使用者確認測試都正確，明確授權合併至 GitHub。
- **作法：**fetch 確認遠端 main 未有新增提交；更新 PIR_MUSIC_GUIDE.md 的驗證／版本狀態，提交後將 feature/pir-music 快轉合併至 main，建立帶註解標籤 pir-music-web-validated-20261006，推送 main、功能分支與標籤至既有 origin；以遠端 SHA 核對結果。
- **驗證：**實機正確由使用者回報，未提供逐項情境紀錄，不推論所有卡片、故障情境或瀏覽器皆已驗證。先前 10 個 Python 與網頁 JavaScript 模擬測試通過，詳見 CHG-20261006-006。本次僅更新文件與版本指標，無程式邏輯變更，不重複執行既有測試。
- **影響：**保留首次高電位／後續低→高觸發、非同步音樂、5 秒網頁提示與 RAM 次數／時間快取；私人 config.py 不上傳，公开 config.example.py 包含部署所需參數。
- **部署／回復：**詳見 PIR_MUSIC_GUIDE.md；確認版以 pir-music-web-validated-20261006 標籤取得，整合前已確認 RFID 版仍為 rfid-validated-20261006。乾淨工作目錄使用 git switch -c restore-pir-web pir-music-web-validated-20261006 建立回復分支，再部署至 ESP32；私人配置另行保留，不使用 force push 或 reset --hard。

## CHG-20261006-006｜網頁顯示移動提示與音樂狀態

- **類別：**需求變更。
- **日期／開始時間：**2026-10-06 02:41:04 +08:00。
- **測試完成／紀錄時間：**2026-10-06 02:43:22 +08:00。
- **先前故障確認：**使用者表示原先未重新上傳 config.py，更新後 PIR 與音樂已正常；實機測試精確時間未提供。CHG-20261006-005 的首次高電位與診斷修正仍保留，不將可能原因誤記為已確認實機根因。
- **原因：**使用者同意在同一偵測事件播放 ESP32 音樂並於網頁顯示「偵測到移動物」，保留提示至少 5 秒及最後時間、次數、播放狀態。
- **作法／呼叫：**新增 hardware/motion.py 狀態工廠；main 建立共享 RAM 字典，注入 Web Server 並傳給 PIR／播放任務。PIR 更新高電位、狀態、偵測提示、最後裝置時間與次數；播放任務更新 playing/completed/error/stopped。/api/data 加入 motion 快照；index.html 用既有每秒 fetch 與 textContent 顯示新卡片，網路失敗標示資料與播放狀態未知。
- **資料生命週期：**首次高或低→高每次觸發增加 count，播放 Event 仍合併待播，因此計數不是播放次數。提示在高電位持續，回低後使用 ticks_ms/ticks_diff 檢查至少 5000 ms 保留期；下次輪詢才清除。錯誤優先顯示異常。最後時間、次數、事件與狀態僅存 RAM，重啟清空，不寫 Flash 或保留完整歷史。
- **驗證：**10 個 Python 測試通過，新增提示時間邊界／tick 回繞／持續高／計數快取驗證並檢查 API motion 預設 JSON；網頁實際 JavaScript 在模擬 DOM/fetch 下驗證提示、等待、次數、時間、播放狀態、錯誤與斷線恢復通過。未做新版網頁的 ESP32 實機或瀏覽器布局驗證。
- **影響／限制：**ESP32 喇叭仍為唯一播放來源，未加瀏覽器音訊或移動 MQTT。播放狀態不保證實際有聲，短狀態可能被 1 秒輪詢略過。私人配置本次不需新增參數。
- **部署／回復：**部署 main.py、tasks.py、web_server.py、index.html、hardware/motion.py，保留已正常的其他硬體模組與 config.py，重啟以更新 HTML 快取。詳見 PIR_MUSIC_GUIDE.md；回到網頁整合前可使用 7f2c0d4，完整 RFID 基線仍為 rfid-validated-20261006。Git 不會自動恢復裝置 Flash 與私人配置。
- **版控：**提交本地 feature/pir-music；待使用者確認新網頁實機結果再合併／推送。

## CHG-20261006-005｜修正首次高電位不觸發並增加 PIR／喇叭診斷

- **類別：**BUG。
- **日期／紀錄時間：**2026-10-06 02:32:54 +08:00（開始檢查時間）。
- **現象：**使用者回報整合後感測不到、沒有聲音；尚未取得實機啟動日誌，不能宣稱已確定或排除接線／部署問題。
- **已確認的程式問題：**首次高電位被當基準忽略，持續高電位時永遠不觸發；喇叭初始化失敗也使 PIR 被略過，缺少診斷訊息。裝置未更新 config 或載入 ns_tools 的其他依賴失敗也是可能原因，並非已確認的實機根因。
- **作法：**首次高電位觸發一次，後續仍採低→高且持續高不重播；main 分開初始化 PIR／喇叭；印出腳位、初始／變化／每 20 次取樣讀值、任務啟動或略過，以及播放完成。Speaker 僅保留範例五個音符頻率，不再依賴 ns_tools；PWM 使用與範例相同的先建立、再 duty/freq 設定方式，設定失敗釋放資源。新增參數缺少時使用範例預設值，避免未更新裝置私人 config 直接停用功能。
- **影響：**開機或感測錯誤恢復後首次為高也可能播放一次；暖機訊號仍可能觸發。其他功能與私人配置不變；自訂音符需擴充模組頻率表。Web 與 MQTT 未修改。
- **驗證：**9 個桌面 Python 測試通過，調整首次高電位預期，保留事件合併、非同步播放與清理測試；未實機驗證。PIR_MUSIC_GUIDE.md 更新機制與獨立 PWM 測試方式。
- **部署／回復：**更新 main.py、tasks.py、hardware/sensors.py、hardware/speaker.py 後重啟；回報初始化與讀值日誌以進一步定位。仍可用 rfid-validated-20261006 回到已確認 RFID 版，或 1735948 檢視修正前 PIR 版。提交本地 feature/pir-music，不合併或推送。

## CHG-20261006-004｜整合 PIR 移動與非同步音樂播放

- **類別：**需求變更。
- **日期／作業開始時間：**2026-10-06 02:22:36 +08:00。
- **測試完成／紀錄時間：**2026-10-06 02:24:45 +08:00。
- **原因：**使用者同意參考單檔範例將 PIR 與無源喇叭接入 main；原範例同步 sleep 會阻塞其他協程，持續高電位也會反覆觸發，採用已確認的非同步播放與低→高觸發策略。
- **作法：**hardware/sensors.py 新增 PirSensor（GPIO 4）；新增 hardware/speaker.py（GPIO 6 PWM），沿用 ns_tools.NOTE_FREQS，以 await uasyncio.sleep 播放 C4/E4/D4/G3 各 0.3 秒加 0.2 秒休止。config.py 與 config.example.py 同步非機密腳位、500 ms 輪詢、512 占空比與旋律，私人 WiFi 值保留。
- **呼叫／生命週期：**main 初始化兩個硬體與獨立 Event，加入 PIR 偵測及播放任務。首次取樣建立基準，後續低→高才 set；播放任務 wait 後先 clear，再播放。Event 合併播放中多次觸發為最多一次待播，不累積計數或歷史；重啟清空事件與基準。播放 finally 靜音，main finally 釋放 PWM；初始化失败略過該功能，讀取／播放例外記錄並延遲重試。
- **影響：**不變更 RFID／LED／Web／MQTT 行為，未新增網頁或移動 MQTT 發布；ns_tools 原同步播放函式及单檔範例不改。500 ms 取樣可能漏掉短脈衝，未新增 PIR 暖機遮蔽；PWM 與音量需實機確認。
- **驗證：**9 個 Python 測試通過（3 個新增 PIR／音樂測試與 6 個 LED／RFID 回歸），涵蓋邊緣觸發、初始高電位、持續高電位、事件合併、協程讓出、音符與休止、錯誤／取消後靜音及重複釋放。既有 RFID 網頁 JavaScript 測試通過。均為桌面 fake 測試，未執行 ESP32 聲音、接線或時序實機驗證。
- **部署／回復：**詳見 PIR_MUSIC_GUIDE.md；部署 main/tasks/sensors/speaker 並新增裝置私人配置。回復使用 rfid-validated-20261006 標籤，重新部署舊應用；私人 config.py 不由 Git 回復。
- **版控：**在 feature/pir-music 本地提交；依已確認方案，等待使用者實機確認再合併與推送。main 與 GitHub RFID 標籤保持既有版本。

## CHG-20261006-003｜保存使用者確認正常的 RFID 版本

- **類別：**需求變更（版本發布與驗證紀錄）。
- **日期／紀錄時間：**2026-10-06 01:29:37 +08:00；實際實機測試時間未提供。
- **原因：**使用者回報目前 RFID 功能正常，明確要求進版本並推送 GitHub。
- **驗證來源：**ESP32 實機正常由使用者確認；未提供逐項驗收紀錄，不推論所有錯誤情境、卡片種類或瀏覽器皆已驗證。先前桌面 6 個 Python 測試及 JavaScript 測試結果仍見 CHG-20261006-002。本次沒有程式邏輯變更，不重複執行相同測試。
- **作法：**fetch 核對遠端；更新 RFID_INTEGRATION.md 的驗證／版本狀態；提交紀錄後，將 feature/rfid-integration 快轉合併至 main，建立帶註解標籤 rfid-validated-20261006，推送 main、功能分支與標籤至既有 origin。保留原基線標籤，完成後核對遠端 SHA 與工作目錄。
- **影響：**RFID 實作維持 6e341b6 的內容，只更新文件與版本指標；私人設定與備份仍排除於 GitHub。版本及 push 成功以 Git refs 為準。
- **回復：**乾淨工作目錄執行 git switch -c restore-before-rfid baseline-before-rfid-20261006 可取得整合前基線；執行 git switch -c restore-rfid rfid-validated-20261006 可取得此次確認版本。Git 切換後仍需自行部署到 ESP32，私人 config.py 另行保留／回復，不採 reset --hard 或 force push。

## CHG-20261006-002｜將 RFID 接入模組化程式與 Web 顯示

- **類別：**需求變更；連帶修正 API JSON 與網頁零值顯示 BUG。
- **日期／紀錄時間：**2026-10-06 00:31:46 +08:00。
- **需求原因：**使用者同意參考單檔範例整合 RFID，並保存可恢復的修改前版本。
- **作法：**新增 hardware/rfid.py，延後明確匯入 MFRC522Async、to_hex_string，沿用配置腳位與 request(REQIDL) → anticoll() → 完整 raw_uid 轉換。main 初始化 RFID 與共享字典，注入 Web Server 並加入 gather；tasks 每輪讀取後等待 500 ms，成功更新最後識別碼與装置時間，例外保留最後紀錄並持續重試。
- **Web 資料：**/api/data 回傳 rfid.status、last_uid、last_read_at、error；API 只複製快取、不直接讀 SPI。以 ujson/json.dumps 取代手組 JSON，避免 None 產生非法 JSON，並跳脫字串。index.html 新增最後讀取卡片區，沿用每秒刷新，以 textContent 顯示；零值使用 ?? 保留，檢查 HTTP 狀態，成功恢復連線顯示。
- **生命週期／影響：**最後紀錄只在 RAM，成功覆寫、無回應保留、重啟清空；讀取例外後下一次成功才清除錯誤。初始化失敗跳過讀卡、保留其他功能。沿用驅動 5-byte 結果（含 BCC），未新增長 UID、刷卡歷史、寫卡、RFID MQTT 或門禁。request 無法區分無卡與部分通訊失敗，ready 只代表已初始化。
- **驗證：**6 個 Python 測試通過（3 個原有 LED 測試及 3 個 RFID／API 測試）；實際網頁 JavaScript 在模擬 DOM/fetch 下驗證初始值、讀卡顯示、零值、錯誤字串、連線失敗與恢复通過。未做 ESP32 實機、SPI 接線或瀏覽器視覺驗證。
- **部署／回復：**詳見 RFID_INTEGRATION.md；部署新硬體模組及四個應用檔案，確認 /lib 驅動與 aiot_tools 依賴後重啟。修改前標籤 baseline-before-rfid-20261006 已推送，基線 commit 為 38a65fd；使用乾淨工作目錄建立回復分支並重新部署。私人配置由本機備份另行處理。
- **版控：**在 feature/rfid-integration 提交並推送；待 ESP32 實機驗證後再合併 main。Git refs 為推送結果依據。

## CHG-20261006-001｜保存 RFID 整合前基線

- **類別：**需求變更。
- **日期／紀錄時間：**2026-10-06 00:26:05 +08:00。
- **原因：**使用者同意 RFID 整合與 GitHub 版本保存；原提交未包含新加入的 Microdot 與個人 VS Code 設定。
- **作法：**納入本機既有 Microdot 2.4.0 套件；同步去除私人 WiFi profiles 的單檔範例；保留個人 settings.json，新增可攜的 settings.example.json；排除 typings 與 .local-backups。私人 config.py、單檔原稿及 settings.json 複製至 .local-backups/baseline-before-rfid-20261006（只留本機）。
- **版本保存：**提交後建立 baseline-before-rfid-20261006 標籤並推送 main 與標籤；以 Git refs 核對實際結果。
- **影響／限制：**此基線不變更應用邏輯；Microdot 是使用者已有的檔案，尚未驗證 ESP32 實機。GitHub 不含私人配置；本機備份不是異地備份。
- **回復：**在乾淨工作目錄使用 git switch -c restore-before-rfid baseline-before-rfid-20261006；需部署時以此版本覆蓋裝置檔案，私人配置另從本機備份取回。個人 VS Code 設定不由 Git 恢復。

## CHG-20261005-003｜納入教學文件與公開範例，推送 GitHub

- **類別：**需求變更。
- **日期／作業開始時間：**2026-10-05 21:49:32 +08:00。
- **紀錄時間：**2026-10-05 21:49:32 +08:00。
- **目的地：**`https://github.com/nschou/IoT_Course.git`。
- **需求來源：**使用者已建立 repository，明確要求將此專案推送至該目的地。

### 原因與作法

1. 檢查遠端既有 refs，確認目前無分支，使用本地 `main` 建立遠端基線，不採 force push。
2. 將獨立 `WEB_UI_EXECUTION_GUIDE.md` 講義與 `AGENTS.md` 中的 Mermaid 11.13.0 規則納入版本快照。講義前次建立及修正時依使用者指示未更新 ChangeLog；本項只記錄此次納入版控／交付，保留先前紀錄方式。
3. 講義的 `Loop` 參與者名稱已改成 `Scheduler`；時序訊息中的分號已改為 `#59;`。講義 12 個圖已用 Mermaid 11.13.0 實際解析通過；這不等於已在所有編輯器驗證視覺布局。
4. 納入現有的 `ESP32上無源按鈕的asyncio版本.md` 教學文件，保留原內容。此項不代表已實作或驗證文件內的按鈕範例。
5. 檢查新單檔範例 `99_All-11-2.py`，發現其 WiFi profiles 含私人值；保留原檔不修改，新增 ignore 規則並建立 `99_All-11-2.example.py`，僅以示範 SSID／密碼取代 profiles，保留其餘程式內容。
6. 在版控指南補充此次 GitHub 目的地及單檔範例部署方式。推送前檢查暫存內容與全部 commit 中的已知私人 WiFi 值及常見 token／私鑰特徵。
7. 設定 `origin` 為使用者指定的網址，提交交付檔案並推送 `main`，完成後核對本地 HEAD 與遠端 main 是否一致；提交／推送結果以 Git refs 為準。

### 影響與驗證範圍

不變更目前裝置應用邏輯或本機連線配置。本機 `config.py` 與 `99_All-11-2.py` 不在 Git 內，新環境需使用相應範本建立設定／範例並自行填入 profiles。單檔範例只是去除私人設定，尚未做 ESP32 實機驗證。秘密掃描只涵蓋已知值與指定模式，不宣稱可辨識所有機密。

## CHG-20261005-002｜建立變更追蹤與本地 Git 版控流程

- **類別：**需求變更。
- **日期：**2026-10-05。
- **作業開始／首次紀錄時間：**12:52:56 +08:00。
- **狀態：**本地 `main` 已初始化；本紀錄隨初始基線提交保存，實際 commit 以 `git log` 查詢。
- **文件與驗證完成時間：**2026-10-05 12:58:12 +08:00；初始提交時間由 Git 記錄。
- **需求來源：**使用者要求所有修正持續記錄日期、時間、原因與作法，並提供每個版控目的所需的指令。

### 原因與目的

先前修改只存在於對話與檔案內容，缺少集中、持續、可追溯的變更歷史。工作目錄檢查時尚未建立 Git repository。另發現 `config.py` 包含實際 WiFi 密碼，不適合直接納入可能分享的版本庫。

### 作法

1. 新增本檔案，追記本次 LED BUG，並定義後續紀錄欄位與時間規則。
2. 新增 `GIT_VERSION_CONTROL.md`，說明初始化、檢查差異、暫存、提交、分支、合併、撤回、標籤、遠端協作與備份的目的及 PowerShell 指令。
3. 新增根目錄 `AGENTS.md`，要求後續協作者／代理在修改時同步更新 ChangeLog，並記錄測試結果，不得捏造時間或驗證。
4. 新增 `.gitignore`，排除本機 `config.py`、秘密、Python 快取與暫存輸出；新增 `.gitattributes` 統一文字檔案儲存為 LF，並將 `.12` 點陣字型標示為 binary，避免改寫二進位內容。
5. 從目前 `config.py` 製作 `config.example.py`，保留非機密設定，只以示範 SSID／密碼替代 WiFi profiles，作為可追蹤的設定範本。
6. 準備本地 `main` 分支與初始快照；不建立未經指定的遠端，也不自動 push。本機仍使用原有 `config.py`，不變更裝置連線設定。

### 影響與限制

- 此項主要改善變更追溯與交付流程，不修改 LED 或感測器的執行邏輯。
- 因排除整份本機 `config.py`，任何非機密設定修正必須同步到 `config.example.py` 才會進入 Git 歷史。
- 新 clone 的環境需由範本建立 `config.py`，填入本機 WiFi 設定；其內容不由 Git 備份。
- 原始修正前的版本未在 Git 中保存，初始提交只能記錄目前修正後基線，不能當作具有完整歷史的前後差異。
- 本地 Git 歷史不等於異地備份；遠端網址未提供，遠端建立與上傳留待設定。

### 驗證方式

三項 LED 桌面回歸測試再次通過。`config.example.py` 的 WiFi profiles 已驗證只有示範值；`git check-ignore` 確認本機 `config.py` 被排除。暫存內容掃描未找到原 WiFi 密碼或常見 GitHub token／私鑰特徵；新文件與測試的空白檢查通過。此掃描只涵蓋上述模式，不代表能辨識所有機密。字型指定為 binary，提交前比對暫存與工作檔 bytes；實機驗證仍未執行。

在不提供檔案擁有權的 G 槽上，部分 Git 執行環境回報 dubious ownership；版控操作僅用 `git -c safe.directory='<本專案確切路徑>' ...` 指定本次指令信任，未設全域萬用信任。

## CHG-20261005-001｜按鈕 1 換色索引反覆為 1，LED 閃爍後熄滅

- **類別：**BUG。
- **修正日期：**2026-10-05。
- **修正時間：**前一輪修正未記錄精確時間，無法可靠追溯；不補造時間。
- **追記時間：**2026-10-05 12:52:56 +08:00。
- **版本／狀態：**目前工作目錄已套用修正；此修正在建立 Git 前完成。

### 預期行為

按鈕 1 每次按下，LED 色碼應以 0～7 循環，並保持該顏色直到下一次操作；色碼 0 為黑色／全滅。開機初始化顯示白色 7，因此第一次按下會切換到 0，之後依序 1、2、3、4、5、6、7、0。

### 實際現象

使用者回報每次都印出藍色／索引 1，LED 短暫閃亮後熄滅：

```text
[Button] 按鈕 1 被按下
[LED] 顏色改變為: 藍 (索引: 1)
[Button] 按鈕 1 被釋放
```

### 原因分析

1. `button1_task()` 呼叫 `rgb_led.next_color()`，依目前色碼計算 `(current_color_index + 1) % 8`。
2. `light_sensor_task()` 同時每 50ms 讀取 ADC；亮度大於 1100 時呼叫 `rgb_led.off()`。
3. 修正前 `off()` 呼叫 `set_color_by_index(0)`，同時熄滅 GPIO 並把目前色碼改成 0。
4. 結果是按鈕短暫設定色碼 1，隨後被光感任務清除；下一次又從 0 切換到 1。

根因為兩個任務共同寫入同一 LED，且「暫時熄燈」與「選擇黑色」共用同一狀態。問題不是 `% 8` 的循環公式。

### 詳細作法

| 檔案 | 修改 | 目的 |
|---|---|---|
| `config.py` | 新增 `LIGHT_AUTO_CONTROL_ENABLED = False` | 預設保留手動選色，不讓光感覆寫 |
| `tasks.py` | 持續讀取 ADC，但只在上述開關為 True 時執行光感控制 | 保留亮度功能，分離感測與控制 |
| `hardware/led.py` | 新增 `is_on`，色碼設定時同步更新 | 分開所選顏色與輸出開關狀態 |
| `hardware/led.py` | `off()` 只將三個 GPIO 設為 0，保留 `current_color_index` | 熄燈不重設循環起點，允許自動亮燈恢復原色 |
| `hardware/led.py` | `toggle()` 依 `is_on` 判斷開關；重新開啟使用所選色碼，色碼為 0 時用白色 7 | 配合新的狀態語意 |
| `tests/test_led_control.py` | 新增 fake GPIO 與光感任務回歸測試 | 驗證循環、保持、恢復與 toggle |
| `SYSTEM_ARCHITECTURE.md`、`IOT_ARCHITECTURE_TECH_TREE.md` | 加入 2026-10-05 修正說明 | 保留修正前架構分析並註明現況差異 |

此處採最小修正，尚未建立完整 LedController、命令佇列或 AUTO／MANUAL 仲裁。若再次啟用光感自動控制，亮時仍會熄燈，這是設定所允許的自動行為；只有色碼不再被清除。

### 訊息位置

修改當時，`tasks.py` 第 33 行印出該訊息：

```python
print(f"[LED] 顏色改變為: {color_name} (索引: {next_color})")
```

後續行號可能變動，可用 `rg -n '顏色改變為' tasks.py` 重新查詢。

### 驗證與結果

已在桌面 Python 使用 fake GPIO 執行三項回歸測試，全部通過：

1. `test_button_colors_survive_light_polling_and_wrap`：1～7→0→1 循環，在亮／暗／遲滯區間讀取後仍維持索引與輸出。
2. `test_auto_off_preserves_color_and_dark_restores_it`：啟用自動控制時，亮處熄燈但保留紅色索引 4，暗處恢復紅色。
3. `test_toggle_restores_selected_color`：關閉再開啟，恢復選定黄色索引 6。

```powershell
python -B -m unittest discover -s tests -v
```

測試使用實際 LED 類別與從 `tasks.py` 擷取的光感任務，在桌面模擬執行；沒有驗證按鈕電氣訊號、實機排程或 LED 接線。使用者尚未回報上傳後的實機結果。

### 部署與回復

- 將更新的 `config.py`、`tasks.py`、`hardware/led.py` 上傳 ESP32 後重新啟動；第一次按下由白色 7 切至黑色 0，屬預期行為。
- 若要測試自動照明，在本機設定與範本將 `LIGHT_AUTO_CONTROL_ENABLED` 改為 True，另開變更紀錄；這不是完整撤回此次 BUG 修正。
- 此修正前沒有 Git commit；不能使用 `git revert` 取得原始修正前版本。日後已提交的修正可依 Git 指南使用 revert，並記錄原因。

## 後續紀錄範本

```text
## CHG-YYYYMMDD-NNN｜變更摘要
- 類別：BUG | 需求變更（實際選一項）
- 修正／完成日期：YYYY-MM-DD
- 修正／完成時間：HH:mm:ss +08:00
- 紀錄時間：YYYY-MM-DD HH:mm:ss +08:00
- 版本／狀態：分支、版本標籤或待提交

### 原因
預期、現象、根因，或需求來源與目的。
### 作法
修改檔案、行為差異、選擇理由與取捨。
### 驗證
指令、結果、實機／模擬範圍、未驗證項目。
### 影響與部署／回復
相容性、需要上傳的檔案、設定與回復方式。
```
