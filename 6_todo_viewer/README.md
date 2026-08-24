# ⑥ 6_todo_viewer —— BPM 待辦與流程查詢器

輸入**員工編號或姓名**，查出這個人的待簽核、我申請的、我經辦過的三類單據，
點單號看表單內容與簽核歷程，每筆都附深連結直接跳回 BPM ——
待簽核給「簽核」，三個分頁都給「追蹤」。

**唯讀**：只有 GET 端點，不存在寫入路徑，也不呼叫任何 SOAP API。

- 計畫與決策記錄：[PLAN.md](PLAN.md)
- 待辦查法的實測依據：[docs/待辦狀態語意.md](docs/待辦狀態語意.md)

---

## 快速開始

後端（預設只綁 127.0.0.1）：

```bash
cd 6_todo_viewer/backend && pip install -r requirements.txt
```

```bash
cd 6_todo_viewer/backend && python -m uvicorn app.main:app --port 8100
```

前端（開發模式，會把 `/api` proxy 到 8100）：

```bash
cd 6_todo_viewer/frontend && npm install && npm run dev
```

正式使用時先 `npm run build`，後端會直接吐 `frontend/dist`，
只需跑 uvicorn 一個 process，開 <http://127.0.0.1:8100> 即可。

資料庫連線沿用 `3_db_explorer/.env`，不必另外設定。

---

## 驗證

```bash
cd 6_todo_viewer/backend && python -m pytest tests -q
```

23 項：XML 解析、兩種深連結、狀態對照、欄位中文名為純邏輯測試；
其中 9 項整合測試需要連得到 191，連不上時會**明確跳過並說明原因**，不會靜默通過。

重跑 P0 的資料來源驗證（含對 SOAP `fetchWorkItemCount` 的交叉比對）：

```bash
cd 6_todo_viewer && python probe_todo.py
```

---

## 三個容易踩的雷

**1. 待辦不在 `WorkItem.performerOID`**

那一欄是「誰做的」，關卡完成時才寫入。未完成的關卡該欄是 NULL ——
實測 824 筆未完成工作項目中只有 1 筆對得到 `Users`。
待辦收件匣是 **`LocalToDoWorkItem`**（`userOID` + `workItemOID`），
也是通知信的來源。細節見 `docs/待辦狀態語意.md`。

**2. 同一個人有多個帳號**

不同公司別是不同帳號（信裡那句「若需追蹤不同公司別之流程，請先登出 BPM」就是這個意思）。
實測「蔣佳緯」在 191 有 8 個帳號。**查詢一律回候選清單讓人挑，程式不自動選第一筆。**

**3. `LocalRelevantData` 一張單有多列，表單只是其中一列**

其餘是 `processSerialNumber`、`isSeparateByVerNo` 這類流程變數。
把表單併進主查詢又用 `SELECT TOP 1` 而不排序，會隨機撞到變數列、
`FormInstance` 接成 NULL，畫面就變成「表單單號 —」＋「表單欄位（0）」。
191 實測 836 張進行中的單，**這樣接會有 383 張（46%）抓不到表單**。

正確做法是把表單單獨查一次，並用 `JOIN FormInstance`（而非 `LEFT JOIN`）
把非表單的列篩掉 —— 見 `service._FORM_SQL`，迴歸測試在
`tests/test_service.py::test_instance_finds_form_when_relevant_data_has_variables_first`。

> `BPMbackend/db/controllers/BPM/BPMGeneralController.js` 的查詢是同一種接法，
> 應該也有這個問題，只是症狀取決於 SQL Server 回傳的列順序。

---

## 兩種 BPM 深連結

| 連結 | 用途 | 需要什麼 | 出現在 |
| --- | --- | --- | --- |
| **簽核** `PerformWorkFromMail` | 直接開簽核畫面 | `Users.id` + `WorkItem.OID` | 待簽核 |
| **追蹤** `TraceProcessMain` | 唯讀檢視整張單與流程圖 | `Users.id` + **`ProcessInstance.OID`** | 三個分頁都有 |

```
{web base}/NaNaWeb/GP/WMS/TraceProcess/TraceProcessMain
    ?hdnMethod=traceProcessFromMail
    &hdnCurrentUserId={Users.id}
    &hdnProcessInstOID={ProcessInstance.OID}
```

追蹤網址不需要工作項目，所以**已結案、我申請的、別人待簽的單都連得到**。

格式不是猜的：BPM 自己寄的通知信正文就有這條，存在 `Mails.message`（30,510 筆）
與 `ProcessNotification.message`（261 筆）。`hdnProcessInstOID` 是
**`ProcessInstance.OID` 而非 `contextOID`** —— 取樣信件裡的 60 個 OID，
60 筆全部對到 `OID`、0 筆對到 `contextOID`。

## 主機切換

| key | 資料庫 | BPM 網站 | 說明 |
| --- | --- | --- | --- |
| `191` | 10.10.130.191 | http://10.10.130.191:8080 | 測試區，預設 |
| `190` | 10.10.130.190 | http://10.10.130.190:9090 | 正式區，唯讀 |

深連結**跟著資料來源走**：查哪一區的資料就給哪一區的網址。
程式只是產生一條連結給人點，本身不對該主機發出任何請求。

正式區的帳密用環境變數覆寫，不寫進 `.env`：

```bash
set BPM_DB_USER_190=<唯讀帳號> && set BPM_DB_PASSWORD_190=<密碼>
```

主機清單可用 `BPM_TODO_HOSTS` 覆寫，格式
`key|標籤|資料庫位址|是否正式區|網站位址`，多筆以逗號分隔。

---

## 欄位的中文名從哪來

詳情抽屜的每個欄位顯示「中文名（欄位 ID）」。中文名不存在單據資料裡，
是從 `FormInstance.definitionOID` → `FormDefinition.defSerialize` 解析出來的，
解析沿用 `bpm_kb.extract` 與 `core.form_handler`（與 `4_db_viewer` 同一套，不另寫）。

用 `definitionOID` 而非表單 ID 去查，是為了對到**這張單當時用的那一版**定義 ——
表單改版後欄位名會變，用最新版會對錯。

一份定義的 XML 動輒 1MB、解析約 90ms，故以 `definitionOID` 為 key 在記憶體快取；
定義內容不會變，要清掉就重啟服務。

取不到中文名時（定義被刪、解析失敗）**欄位值照樣顯示**，只是名稱位置顯示 ID，
並在畫面上標明原因 —— 不會因為拿不到名稱就讓整張單看不到。

## 已知限制

- `WorkItem.currentState = 97` 的卡住關卡不計入待辦數（與 BPM 一致），
  但會在清單裡以「異常 97」標示，不靜默丟棄。
- `WorkItem.currentState = 2` 的語意未知：取樣中沒有真人案例，
  目前不計入待辦。
- **Grid 的欄位（列內 item）沒有中文名**。Grid 本身有（型別 `LIST`，例如
  `Grid_DocServer` →「設定文件主機」），但欄位的中文名不在 `defSerialize` 的
  元件清單裡 —— `core.form_handler` 掃不到，`4_db_viewer` 也同樣看不到。
  因此 Grid 的表頭維持顯示 item 的 ID。
- 有些欄位的「中文名」其實是元件的預設名（例如 `sqrbmxm` 顯示為 `TextBox`），
  那是表單定義裡就沒有配到標籤，不是解析錯誤 —— 與 `4_db_viewer` 顯示的一致。
