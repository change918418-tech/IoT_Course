# Git 版控作法與指令：物聯網軟體架構教學專案

## 1. 本專案採用的規則

Git 保存可回溯的快照；`ChangeLog.md` 保存為何變更與驗證範圍。兩者搭配，才能回答「何時變更、改了什麼、為何這樣做」。本指南使用 Windows PowerShell，指令中的示例網址、版本與 commit ID 必須換成實際值。

- `main` 保存可交付的基線；開發可用 `fix/...`、`feature/...`、`docs/...` 分支。
- 每一個修正／需求提交包含相關程式、必要測試與 ChangeLog；不要把无關變更混成一筆。
- 本機 `config.py` 含私人設定，不納入 Git；`config.example.py` 保存非機密配置。新環境先複製範本，再填入 WiFi profiles。
- 初始化只能保存當前基線；建立 Git 前的變更已由 ChangeLog 追記，沒有自動生成完整舊版本。
- 這次只建立本地版控，未指定遠端。不要以同步磁碟取代 Git 協作；避免兩台電腦同時寫同一份 `.git`，多台電腦各自 clone 再透過遠端交換提交。

> 2026-10-05 後續交付更新：使用者已指定 GitHub repository `https://github.com/nschou/IoT_Course.git`，本次依授權設定 `origin` 並推送 `main`；下面未指定遠端的描述為初始化時狀態。可用 `git remote -v`、`git ls-remote origin refs/heads/main` 核對目前狀態。

新增單檔範例也採相同機密排除策略：本機 `99_All-11-2.py` 不追蹤，公開版本為 `99_All-11-2.example.py`。新環境若要使用它，先複製至所需檔名並填入自己的 WiFi profiles；不要直接覆蓋已有私人設定的檔案。該範例不是目前主程式的必要依賴。

## 2. 概念與檢查位置

| 區域 | 目的 | 檢查指令 |
|---|---|---|
| 工作目錄 | 目前正在編輯的檔案 | `git status --short`、`git diff` |
| 暫存區 index | 決定下一次提交的內容 | `git diff --cached` |
| 本地歷史 | 已提交、可比較與回復的快照 | `git log --oneline --decorate --graph` |
| 遠端 | 分享提交、協作與異地備份 | `git remote -v`、`git fetch origin` |

`git diff` 不顯示未追蹤新檔內容；先看 `git status`，暫存後用 `git diff --cached` 檢查新檔。`.gitignore` 不會自動移除已追蹤的檔案，參考 [Git ignore 文件](https://git-scm.com/docs/gitignore)。

## 3. 進入專案與確認工具

**目的：**避免在錯誤目錄建立或操作 repository。

```powershell
Set-Location -LiteralPath 'G:\AsusWebStorage\2025\00_Teaching\114-1-csie@nuu\114-1-物聯網軟體架構\99_All_07_refactor'
Get-Location
git --version
git status
```

尚未初始化時，`git status` 回 `not a git repository` 是預期結果；已初始化後可用 `git rev-parse --show-toplevel` 確認根目錄。

## 4. 初始化與作者身份

**目的：**建立本地版本庫及提交作者資訊。已初始化的專案不需要重做。

```powershell
git init -b main
git config --get user.name
git config --get user.email
git config --show-origin --get user.name
git config --show-origin --get user.email
```

只有身份缺少或需要專案專屬身份時，填入真實資料，使用本地設定而非影響所有專案：

```powershell
git config --local user.name '你的姓名'
git config --local user.email '你的電子郵件'
```

Git 作者身份不代表遠端登入授權。初始化參考 [git init](https://git-scm.com/docs/git-init)。

若 G 槽不提供擁有權資訊而出現 `detected dubious ownership`，先核對目錄確實屬於本專案；可僅在單次指令指定確切信任路徑，例如：

```powershell
git -c safe.directory='G:/AsusWebStorage/2025/00_Teaching/114-1-csie@nuu/114-1-物聯網軟體架構/99_All_07_refactor' status
```

需要時將同樣的 `-c safe.directory=...` 放在後續 Git 指令的子命令前。不要以 `safe.directory=*` 取消所有目錄的保護。本次操作未修改全域信任設定。

## 5. 排除機密與建立可追蹤配置

**目的：**保留可重現的公開設定，同时避免記錄 WiFi 密碼。

```powershell
git check-ignore -v config.py
git check-ignore -v config.example.py
git status --short --ignored
```

第一條應顯示 `.gitignore` 的匹配規則；範本不應被忽略，該次無輸出且 exit code 1 表示沒有匹配規則。

新 clone 尚未有 `config.py` 時才執行以下步驟，既有環境不要覆蓋私人設定：

```powershell
if (-not (Test-Path -LiteralPath 'config.py')) {
    Copy-Item -LiteralPath 'config.example.py' -Destination 'config.py'
}
```

以編輯器填入本機 `WIFI_PROFILES`。每次改非秘密設定，要同时修改範本並記錄 ChangeLog。此策略的代價是本機秘密設定不由 Git 備份；日後可另做需求變更，將秘密移至 `secrets.py`，再讓正式 `config.py` 進版控。

若機密早已被追蹤，可先將它移出暫存／追蹤並提交：

```powershell
git rm --cached -- config.py
git add -- .gitignore config.example.py ChangeLog.md
git commit -m 'chore(config): stop tracking private device configuration'
```

`--cached` 保留本機檔案，但不會清除舊 commit 中的秘密。已分享的秘密先輪替／撤銷，再規劃歷史清理；不要以為新增 ignore 就能抹除過去。

## 6. 初始基線提交

**目的：**保存目前修正後的完整可追蹤專案。若已建立初始提交，無需重做。

```powershell
git add -- .gitignore .gitattributes AGENTS.md ChangeLog.md GIT_VERSION_CONTROL.md config.example.py
git add -- main.py boot.py tasks.py web_server.py index.html assets hardware communication lib tests SYSTEM_ARCHITECTURE.md IOT_ARCHITECTURE_TECH_TREE.md
git diff --cached --stat
git diff --cached --check
git diff --cached
git ls-files -- config.py
python -B -m unittest discover -s tests -v
git commit -m 'chore: establish version-controlled teaching project baseline'
git status --short
git log -1 --format=fuller
```

`git ls-files -- config.py` 應無輸出。提交前檢查 staged diff 不含秘密；測試失敗需修正或明確記錄範圍，不可記為通過。此提交包含建立 Git 前就已存在的檔案，不代表所有檔案是本次新寫的。

若系統 `python` 不可用，本機可改用目前已知的執行檔：

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -m unittest discover -s tests -v
```

這是本機路徑，其他電腦依自己的 Python 安裝位置調整。

## 7. 日常修改、檢查、提交

**目的：**將一個完整且可說明的變更保存為一筆 commit。

```powershell
git status --short
git diff -- tasks.py hardware/led.py config.example.py
Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
```

在時區為台灣的電腦上記錄上述時間，更新 ChangeLog。其他時區的電腦須轉為 UTC+08:00，不直接照抄當地時間。

```powershell
python -B -m unittest discover -s tests -v
git add -- tasks.py hardware/led.py config.example.py tests/test_led_control.py ChangeLog.md
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m 'fix(led): preserve selected color during light polling'
git status --short
```

只加入實際修改且屬於本次目的的檔案。提交訊息建議使用 `fix`、`feat`、`docs`、`test`、`chore`；ChangeLog 類別仍固定為 BUG／需求變更。

## 8. 分支與合併

**目的：**讓修正與實驗不直接干擾 `main` 基線。

```powershell
git status --short
git switch main
git switch -c fix/led-color-hold
```

完成編輯、測試、ChangeLog 與提交後：

```powershell
git switch main
git merge --no-ff fix/led-color-hold -m 'merge: integrate LED color-hold fix'
git branch -d fix/led-color-hold
```

`--no-ff` 保留分支整合節點。若合併衝突，逐檔確認双方意圖，尤其 ChangeLog 应保留双方紀錄；排除衝突標記後測試、`git add -- <檔案>`、`git commit`。若決定取消尚未完成的合併，使用 `git merge --abort`；合併前先提交或妥善保存工作。

## 9. 暫時保存工作

**目的：**切換任務前保存尚未提交、但可追蹤的工作。

```powershell
git stash push -u -m 'WIP: LED control experiment'
git stash list
git stash apply 'stash@{0}'
git status --short
```

確認套用與處理衝突後，才用 `git stash drop 'stash@{0}'` 移除該暫存。`-u` 包含未追蹤檔，**不包含被忽略的 `config.py`**。不要用 `-a` 將秘密也放進 Git 物件；修改本機配置後自行備份。

## 10. 查詢演變與修改原因

**目的：**回答誰在何時改了某個行為，並對照 ChangeLog。

```powershell
git log --oneline --decorate --graph --all
git log --follow -- ChangeLog.md
git log -p -- hardware/led.py
git blame -L 55,85 -- hardware/led.py
git show HEAD --stat
git show HEAD:hardware/led.py
git diff HEAD~1 HEAD -- tasks.py hardware/led.py
git log --all -S 'LIGHT_AUTO_CONTROL_ENABLED' -- config.example.py tasks.py
```

`HEAD~1` 要有至少兩筆歷史才存在；行號也依當時版本調整。`blame` 顯示最後修改該行的 commit，原因通常要讀 commit 與 ChangeLog，不能只看作者。

## 11. 撤回：依保存位置選對指令

| 目的 | 指令 | 影響 |
|---|---|---|
| 取消暫存，保留工作內容 | `git restore --staged -- tasks.py` | 從下次提交移除，檔案修改仍在 |
| 放棄某檔未暫存修改 | `git restore -- tasks.py` | 工作目錄回到暫存版本；會丟失該部分修改 |
| 放棄該檔全部未提交修改 | `git restore --source=HEAD --staged --worktree -- tasks.py` | 暫存與工作內容均回到 HEAD；先確認無需保存 |
| 撤回已提交的修正 | `git revert --no-commit <COMMIT_ID>` | 準備反向變更，保留歷史；需後續提交 |
| 查找本地分支曾指向哪裡 | `git reflog` | 可協助找回可達 Git 物件，不保證恢復未提交檔 |

已提交修正的撤回流程示例：

```powershell
git status --short
git revert --no-commit '<COMMIT_ID>'
```

若已成功套用反向變更，編輯 ChangeLog：保留歷史紀錄、加入此次撤回原因；執行測試，再提交：

```powershell
git add -- ChangeLog.md
git diff --cached
git commit -m 'revert: withdraw change and document the reason'
```

`<COMMIT_ID>` 必須換成實際 hash；revert 可能反向修改 ChangeLog，提交前須恢復原歷史並追加新紀錄。若有衝突，先解決、暫存，再依 `git status` 指示 `git revert --continue`，或 `git revert --abort` 取消。本例適用一般 commit，merge commit 撤回需另外判斷主線父節點。

建議共享歷史使用 revert，避免用 `reset --hard`／force push 直接改寫大家依賴的歷史；restore 與 revert 的差別參考 [Git 指令文件](https://git-scm.com/docs/git)。

## 12. 版本標籤與查看舊版本

**目的：**為實際驗收過的課程交付版本命名。

先測試、完成 ChangeLog 與提交，再依實際狀態選擇版本號；不要只因有舊版註解就宣稱整個專案是該版本。

```powershell
git tag -a v0.1.0 -m 'Teaching baseline: desktop regression tests passed; hardware pending'
git tag --list
git show v0.1.0 --stat
git diff v0.1.0 HEAD --stat
git switch -c inspect/v0.1.0 v0.1.0
git switch main
```

範例標籤清楚註明只做桌面測試。發布後不要任意移動既有 tag；後續修正另用新版本。

## 13. 遠端協作與備份

**目的：**將已提交的版本送往使用者指定的遠端，取得協作與異地保存。此專案目前尚未設定目的地，以下是手動流程，不表示已執行。

先在所選服務建立空的 private repository，再用真正網址取代示例：

```powershell
git remote add origin 'https://YOUR_GIT_HOST/YOUR_ACCOUNT/YOUR_REPOSITORY.git'
git remote -v
git push -u origin main
```

若 origin 已存在且需要修正網址，使用 `git remote set-url origin '<實際網址>'`。不要把 token 放在 URL 或文件。push 前確認提交不含秘密，使用遠端服務支援的 SSH／credential manager 登入。

日後更新流程：

```powershell
git status --short
git fetch origin
git log --oneline --left-right main...origin/main
git switch main
git pull --ff-only origin main
git push origin main
```

`--ff-only` 在分岔時停止，避免不知情地自動產生合併；這時檢視双方提交，再明確合併或另開分支處理。功能分支與 tag 各別上傳：

```powershell
git push -u origin fix/led-color-hold
git push origin v0.1.0
```

新電腦另行 clone：

```powershell
git clone 'https://YOUR_GIT_HOST/YOUR_ACCOUNT/YOUR_REPOSITORY.git' 'iot-teaching-project'
Set-Location -LiteralPath 'iot-teaching-project'
Copy-Item -LiteralPath 'config.example.py' -Destination 'config.py'
```

填入本機 profiles，依部署清單准备函式庫并驗證，勿假設 clone 就會自動設定 ESP32 或 WiFi。

## 14. 離線歷史備份

**目的：**在沒有遠端時保存已提交的 Git 歷史。

```powershell
git bundle create 'iot-teaching-history.bundle' --all
git bundle verify 'iot-teaching-history.bundle'
```

將 bundle 複製到另外的備份位置；保留在同一磁碟不能抵抗該磁碟損壞。bundle 不含未提交工作與被忽略的 `config.py`；秘密配置另依私人備份方式處理。需要還原時，可在新的目錄執行 `git clone '備份完整路徑.bundle' 'restore-project'`。

## 15. 每次修正的完成條件

1. 確認變更目的與 BUG／需求變更分類。
2. 修改必要檔案，非機密配置同步範本。
3. 執行適當測試，註明未做的實機項目。
4. 更新 ChangeLog 的台灣日期／時間、根因、作法、影響與驗證。
5. 檢查 staged diff、空白錯誤與機密，提交相關檔案。
6. 必要時標記已驗收版本；已有授權與指定遠端才 push。

更多指令參數可查 [Git 官方指令參考](https://git-scm.com/docs)。
