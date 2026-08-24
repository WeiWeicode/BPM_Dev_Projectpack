# 專案計劃書：BPM 待辦與流程查詢器 (6_todo_viewer)

> 狀態：**P0–P3 已完成**，使用說明見 [README.md](README.md)；**P4（接 190 正式區）待你提供唯讀帳密**。
> P0 推翻了初版 §4.1 的待簽核定義 —— 待辦不在 `WorkItem.performerOID`，
> 在 `LocalToDoWorkItem`。§2.6、§4 已依實測修正。
> 架構：Python FastAPI 後端 + Vue 3 / Vite 前端（沿用 `4_db_viewer` 的形狀）。
> 前置相依：`3_db_explorer`（`bpm_kb.db` 連線層）、`4_db_viewer`（多主機切換模式）。

---

## 1. 執行摘要

### 1.1 背景

BPM 每天寄「您尚有 N 筆未簽核流程通知」的信，信裡是一張表格加一條深連結：

```
http://10.10.130.190:9090/NaNaWeb/GP/PerformWorkFromMail
    ?hdnMethod=performWorkFromMail
    &hdnUserId=GV112001
    &hdnWorkItemOID=b16ac18cf9241004822a71e095b2d9c2
```

痛點是這封信**只涵蓋未簽核**，且只能被動等它寄來：

- 想主動查「我現在有哪些待辦」→ 只能登入 BPM 一頁頁翻
- 想查「我送出去的單跑到哪了、結案沒」→ 信裡完全沒有
- 想查別人（代理、追單）的狀態 → 沒有信可看
- 想在自己開發的應用裡直接跳到那張單 → 需要 `WorkItemOID`，信以外拿不到

### 1.2 產品目標

輸入**使用者 id 或姓名**，一頁列出該人的三類單據與內容，並對可簽核的單提供
一鍵跳轉 BPM 的深連結（等同點信裡那條連結）。

### 1.3 已定案的三項決策

| # | 決策 | 說明 |
| --- | --- | --- |
| 1 | **雙連線，先開發後接正式區** | 191 測試區開發，190 正式區唯讀，接上前需人工確認一次 |
| 2 | **深連結跟著資料來源自動切換** | 查哪一區的資料，就給哪一區的 URL，不需手動設定 |
| 3 | **主資料來源走 SQL，不走 SOAP** | 理由見 3.2 |

### 1.4 與既有專案的分工

| 專案 | 資料來源 | 看的東西 |
| --- | --- | --- |
| 3_db_explorer | 資料庫 | 表單／流程**定義**（設計期） |
| 4_db_viewer | 資料庫 | 表單／流程**定義**（設計期，網頁版） |
| **6_todo_viewer** | 資料庫 | 流程**實例**（執行期）—— 誰的單、跑到哪、內容是什麼 |

界線：4 看的是「這支流程長什麼樣」，6 看的是「這張單現在怎麼了」。
6 **不碰任何定義層的表**，也不提供寫入。

---

## 2. 已驗證事實（2026-08-24 於 191 測試區實測）

動手前先把地基釘住。以下都是實跑 SQL 得到的，不是推測。

### 2.1 狀態代碼分布

`WorkItem.currentState`（全表 3,396,747 筆）：

| 值 | 筆數 | 其中 completedTime 為 NULL |
| ---: | ---: | ---: |
| 0 | 946 | 673 |
| 1 | 354 | 243 |
| 2 | 5 | 5 |
| 3 | 3,354,976 | 21 |
| 4 | 17,812 | 4 |
| 5 | 22,652 | 0 |
| 97 | 2 | 2 |

`ProcessInstance.currentState`：

| 值 | 中文（依 `BPMGeneralController.js` 的對照） | 筆數 |
| ---: | --- | ---: |
| 1 | 進行中 | 836 |
| 3 | 已結案 | 523,503 |
| 4 | 已撤銷 | 17,755 |
| 5 | 已中止 | 10,329 |

> 該對照表另有 `0 未開始`、`2 已暫停`，191 實測沒有任何一筆落在這兩個值。

### 2.2 `WorkItem.OID` 就是深連結要的 OID

`WorkItem.OID` 是 `nchar(32)`，格式與信件 URL 的 `hdnWorkItemOID`
（`b16ac18cf9241004822a71e095b2d9c2`）一致。實測樣本如
`fb81a080ed2e100488ece516992aef6c`。**深連結可以自己組出來。**

### 2.3 同一個人可能有多個帳號

實測 `Users` 表裡 mailAddress 相同的有兩筆：

| id | OID | userName |
| --- | --- | --- |
| GV112001 | `9f24e5f0f76410048c7d2145a2b385cd` | 蔣佳緯 |
| S112009 | `4db90e2cf0151004808a451881bdf758` | 蔣佳緯 |

這對應信裡那句「若需追蹤不同公司別之流程，請先登出 BPM，再重新按連結」——
**公司別不同帳號不同**。因此姓名查詢必須列出候選讓人選，不能自動挑第一筆。

> 另注意 `AGENTS.md` 8.1 的既有坑：使用者 OID 一律取 `Users.OID`，
> 不是 `Employee.OID`，兩者只差一個字元。

### 2.4 191 沒有你的待辦

`GV112001` 在 191 的 `WorkItem` **一筆都沒有**。191 整體有資料到 2026-08-24
（`WorkItem.createdTime` 最大值），但那是別人的單。

**這是「雙連線」決策的直接理由**：功能可以在 191 完整開發驗證，
但要看到信裡那兩張單（`SIC00500000515` / `SIC00500000544`），只能連 190。

### 2.5 P0 的驗證結果

完整過程與數據見 [docs/待辦狀態語意.md](docs/待辦狀態語意.md)，重跑用 `python probe_todo.py`。

| # | 原本的未知 | 結果 |
| --- | --- | --- |
| U1 | `WorkItem.currentState` 0 / 1 / 2 的語意 | **已釘死**：0 與 1 都算待辦，3/4/5/97 不算。以 SOAP `fetchWorkItemCount` 對 6 名使用者交叉驗證全數吻合。`2` 取樣中無真人案例，維持未知 |
| U2 | `currentState = 97` 的 2 筆 | **已查明**：`signoffState = 1` 的卡住關卡，SOAP 不計入。清單排除，但要另闢標記，不靜默丟掉 |
| U3 | 已結案單的「追蹤」URL 格式 | **已解**（2026-08-24 補）：`TraceProcessMain?hdnMethod=traceProcessFromMail&hdnCurrentUserId=…&hdnProcessInstOID=…`，格式取自 BPM 通知信正文（`Mails.message`）。OID 用 `ProcessInstance.OID`，取樣 60 筆驗證 |
| U4 | 代理簽核（`bypassPerformerOID`） | **不影響**：待辦集合中該欄全為 NULL，代理是完成時才落地的資訊。第一版不處理 |

### 2.6 P0 推翻的假設：待辦不在 `performerOID`

初版計畫把待簽核定義成「`WorkItem.performerOID = 我` 且未完成」——**這是錯的**。

| 集合 | 筆數 | 其中 `performerOID` 對得到 `Users` |
| --- | ---: | ---: |
| 未完成工作項目 | 824 | **1** |
| 已完成工作項目 | 3,354,976 | 2,341,243 |

`performerOID` 是「誰做的」，關卡完成時才寫入。待簽核的人存在 **`LocalToDoWorkItem`**
（`userOID` + `workItemOID` + `subject` + `processInstanceName`），那正是通知信的來源。

另外實測：全表 1,367 筆待辦去重後只有 972 個工作項目 ——
**同一關卡可同時派給多人**，清單必須以 `LocalToDoWorkItem` 的列為單位。

---

## 3. 技術決策

### 3.1 沿用既有架構，不新造輪子

| 層 | 做法 |
| --- | --- |
| 連線 | `bpm_kb.db.Database`，`readonly=True`，參數化 `?` 佔位符 |
| 多主機 | 沿用 `4_db_viewer/backend/app/settings.py` 的 `HOSTS` 與 `host_entry()`，正式區帳密用 `BPM_DB_USER_190` / `BPM_DB_PASSWORD_190` 環境變數覆寫 |
| 後端 | FastAPI，**只有 GET**，Pydantic 模型為資料契約唯一真實來源 |
| 前端 | Vue 3 `<script setup>` + TypeScript + Vite，手刻 CSS，composables，無 UI 框架、無 CDN |
| 型別 | `src/api/types.ts` 由後端 OpenAPI 產生，不手改 |

### 3.2 為什麼不用 SOAP 當主要來源

`5_ws_explorer` 有實測過的 `fetchToDoWorkItem(pProcessIds, pUserId)`，看似正合用，
但它**必須指定流程 ID**，無法一次列出某人跨全部流程的待辦（多筆分隔方式也未驗證）。
`fetchWorkItemCount` 只回數量，`pAccessCondition` 的 0/1 語意還是推測。

更關鍵的是：**SOAP 的正式區呼叫被 `AGENTS.md` 8.1 全面禁止**，
而我們要查的正是正式區資料。SQL 唯讀則不在該條禁令內。

結論：主線走 SQL。SOAP 保留為未來補充（例如需要即時欄位模板時），第一版不用。

### 3.3 正式區的防護

`AGENTS.md` 8.1 只規範 SOAP，未規範正式區的唯讀 SQL。既然要連，防護明寫出來：

1. `Database(readonly=True)` —— 連線層就是唯讀
2. 本專案**不註冊任何寫入路由**，不是靠 if 擋（比照 `4_db_viewer` 的 `ENABLE_WRITE` 預設關閉思路，但這裡連旗標都不提供）
3. 190 帳密走環境變數覆寫，`.env` 不進版控、不寫進 API 回應、不進日誌
4. 後端預設只綁 `127.0.0.1`
5. 第 1–3 階段全程用 191，**第 4 階段接 190 前需人工確認**

---

## 4. 資料模型

沿用 `BPMGeneralController.js` 已驗證的關聯，不重寫：

```
ProcessInstance PI
  ├─ LocalRelevantData LRD   (LRD.containerOID = PI.contextOID)
  │     └─ FormInstance FI   (FI.OID = LRD.valueOID)   → fieldValues 是 XML
  ├─ WorkItem WI             (WI.contextOID = PI.contextOID)
  │     ├─ Users U           (U.OID = WI.performerOID) → 已完成關卡的執行者
  │     └─ LocalToDoWorkItem T  (T.workItemOID = WI.OID)
  │           └─ Users U     (U.OID = T.userOID)       → 待簽核的人
  └─ Users                   (U.OID = PI.requesterOID) → 申請人
```

**注意 `PI.contextOID` 不是 `PI.OID`** —— WorkItem 與 LocalRelevantData 都掛在
`contextOID` 上，接錯會查不到東西。

### 4.1 三類清單的定義（P0 實測後）

| 分頁 | 條件 | 排序 |
| --- | --- | --- |
| **待簽核** | `LocalToDoWorkItem.userOID = 我` 且對應 `WI.currentState IN (0, 1)` | `T.createdTime` DESC |
| **我申請的** | `PI.requesterOID = 我`，可再依 `PI.currentState` 篩未結案／已結案／撤銷／中止 | `PI.createdTime` DESC |
| **我經辦過的** | `WI.performerOID = 我` 且 `WI.currentState = 3` | `WI.completedTime` DESC |

待簽核另外要處理的兩件事：

- `WI.currentState = 97` 的卡住關卡**不計入待辦數**，但要以「異常」標記另行呈現
- `LocalToDoWorkItem` 有 26 筆 `userOID` 對不到 `Users`（25 筆系統代理
  `AutoAgent0001`、1 筆已刪測試帳號），依 id／姓名查詢時自然排除，不是資料錯誤

「我經辦過的」筆數很大（全表 335 萬筆是已完成），**必須分頁**，
用 SQL Server 的 `OFFSET ... ROWS FETCH NEXT ... ROWS ONLY`，
並比照既有慣例先跑一次 `COUNT(*)` 取總數。

### 4.2 使用者查詢

- `Users.id` 精確比對（大小寫不敏感）
- `Users.userName` 模糊比對
- 一律回**候選清單**，含 id、姓名、OID、mailAddress，由使用者挑
- `Users.leaveDate` 有值者標記為已離職但不隱藏（追舊單時仍需要）

---

## 5. 深連結

### 5.1 待辦（已知可行）

```
{host 的 web base}/NaNaWeb/GP/PerformWorkFromMail
    ?hdnMethod=performWorkFromMail
    &hdnUserId={Users.id}
    &hdnWorkItemOID={WorkItem.OID}
```

依決策 2，base URL 掛在 host 條目上自動切換：查 191 的資料給 191 的連結，
查 190 給 190。做法是把 `4_db_viewer` 的 host tuple
`(key, 標籤, 位址, 是否正式區)` 擴充一個 web base 欄位，
預設 `191 → http://10.10.130.191:8080`、`190 → http://10.10.130.190:9090`，
可用環境變數覆寫。

> 這只是**產生一條連結給人點**，程式本身不對 190 發出任何 HTTP 請求，
> 與 `AGENTS.md` 8.1 禁止的「呼叫 190 API」不同。

### 5.2 追蹤（已實測，U3 已解）

```
{host 的 web base}/NaNaWeb/GP/WMS/TraceProcess/TraceProcessMain
    ?hdnMethod=traceProcessFromMail
    &hdnCurrentUserId={Users.id}
    &hdnProcessInstOID={ProcessInstance.OID}
```

不需要工作項目，因此**三個分頁都能出這條連結** —— 已結案、我申請的、
別人待簽的單都連得到。待簽核那頁同時給「簽核」與「追蹤」兩個入口。

格式來源是 BPM 自己寄的通知信正文（`Mails.message`、`ProcessNotification.message`），
不是猜的。`hdnProcessInstOID` 是 `ProcessInstance.OID`，**不是 `contextOID`**（取樣 60 筆全數驗證）。

---

## 6. API 設計

全部 GET，唯讀。路徑全小寫，多字用底線（與既有慣例一致）。
所有端點都吃 `?host=191|190`，預設 191。

```
GET /api/hosts                       # 可用主機清單（含 web base、是否正式區）
GET /api/users/search?q=             # id 或姓名 → 候選清單
GET /api/users/{user_id}/todo        # 待簽核
GET /api/users/{user_id}/requested   # 我申請的（?state= 篩選、分頁）
GET /api/users/{user_id}/handled     # 我經辦過的（分頁）
GET /api/instances/{serial_number}   # 單筆詳情
```

`/api/instances/{serial_number}` 的回應比照 controller 既有結構：

| 欄位 | 來源 |
| --- | --- |
| `pi_serial_number` / `fi_serial_number` | `PI.serialNumber` / `FI.serialNumber` |
| `process_instance_name`、`subject` | `PI` |
| `current_state` + `current_state_label` | `PI.currentState` + 中文對照 |
| `field_values` | `FI.fieldValues` XML → 一般欄位 |
| `grid_values` | 同上 → Grid 欄位 |
| `attachments` | 同上 → 附件節點 |
| `approval_history` | `WorkItem` join `Users`，含關卡名、執行者、簽核意見、時間 |

XML 解析邏輯照抄 controller 的 `processFormFields` / `processGridFields` /
`processAttachmentFields` 三個函式改寫成 Python。
**這裡是純讀取**，不涉及 `AGENTS.md` 7.2 的位元組無損回寫要求。

---

## 7. 前端

單頁三區：

1. **搜尋列** —— 輸入 id 或姓名 + 主機下拉（191 / 190）
2. **候選清單** —— 多筆同名或同人多帳號時出現，選定後收起
3. **三分頁清單** —— 待簽核 / 我申請的 / 我經辦過的，每筆一列：
   單號、流程名稱、主旨、關卡、狀態（中文徽章）、時間、「前往 BPM」按鈕
4. **詳情抽屜** —— 點單號展開：表單欄位、Grid、附件、簽核歷程時間軸

樣式手刻，狀態徽章用色票區分進行中／已結案／撤銷／中止。

---

## 8. 分階段執行

| 階段 | 內容 | 完成標準 |
| --- | --- | --- |
| **P0 驗證** ✅ | 釘死 U1–U4，把「id → 三類清單」的 SQL 跑通 | **已完成**：`probe_todo.py` 可重跑，結論見 `docs/待辦狀態語意.md`。U1/U2/U4 已解，U3 仍未解 |
| **P1 後端** ✅ | FastAPI + Pydantic + 六個端點 + pytest | **已完成**：pytest 14 項全綠（含 5 項需連線的整合測試）；六個端點實測回得出資料 |
| **P2 前端** ✅ | 搜尋 → 候選 → 三分頁 → 詳情抽屜 → 深連結 | **已完成**：191 上完整走一輪，待辦數 8 與 SOAP 一致，深連結格式與通知信相同 |
| **P3 打磨** ✅ | 分頁、載入狀態、查無資料的明確提示 | **已完成**：分頁實測 986 筆可翻頁；查無資料顯示「查無資料」；異常關卡另行標示 |
| **P4 接 190** | 多主機切換實接正式區 | 用信裡的 `SIC00500000515`、`SIC00500000544` 當驗收案例，深連結點得開 |

P0 只有 SQL 腳本，不建服務 —— 語意沒確認前寫的程式一定要重寫。

---

## 9. 風險與界線

| 風險 | 對策 |
| --- | --- |
| 誤把 191 的過期資料當成正式資料 | 畫面永遠顯示當前主機，正式區用不同顏色標示 |
| 同名／同人多帳號挑錯 | 一律列候選，不自動挑第一筆（2.3） |
| `WorkItem` 335 萬筆造成慢查詢 | 一律分頁；先確認 `performerOID`、`contextOID` 上的索引狀況 |
| 狀態語意猜錯 | U1 未釘死前不寫死；文件標明哪些是實測、哪些是推測 |
| 正式區帳密外洩 | 走環境變數，不進版控、不進日誌、不進 API 回應 |

**本專案不做的事**：任何寫入、任何 SOAP 呼叫、任何對定義層（`FormDefinition` /
`ProcessDefinition` 等）的查詢。要那些請走 `4_db_viewer`。
