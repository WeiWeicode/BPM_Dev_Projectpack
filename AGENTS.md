# AI Agent 開發規範 —— 鼎新 BPM 快速開發工具集

本檔為 AI agent 在此 repo 工作時的行為準則。專案結構與各子專案用途見
[README.md](README.md)。

---

## 1. 先思考再動手

### 規則
- **動手之前，先說明你的理解與假設**。用 1-3 句話摘要你打算做什麼、為什麼這樣做。
- **有任何疑問，先問，不要猜**。錯誤的假設比多問一個問題代價高得多。
- 如果需求模糊或有多種解讀方式，列出你看到的選項，讓人類選擇。
- **本專案特別注意**：鼎新 BPM 的資料模型反直覺（見第 7 節），
  動手前先確認你對資料流向的理解是對的，不要照著命名猜語意。

### 範例
```
❌ 錯誤：直接開始寫程式碼
✅ 正確：「我理解你想在流程檢視加一欄顯示執行者。我假設要顯示的是
    ParticipantDefinition.participantType（PROCESS_REQUESTER / MANAGER），
    而不是實際的員工姓名。這樣對嗎？」
```

---

## 2. 簡單優先

### 規則
- **用最少的程式碼解決當前問題**，不要加用不到的功能。
- 不要「順便」引入新的套件、設計模式或抽象層，除非任務明確要求。
- 不要寫「未來可能用到」的程式碼。等需要的時候再加。
- 如果一個問題能用 10 行解決，不要寫 50 行。

### 本專案的具體體現
- `1_xml_tool` 只用 Python 標準函式庫，**不要引入 lxml、BeautifulSoup**
  —— XML 必須位元組級無損回寫，通用解析器做不到（見第 7.2 節）。
- `2_web_builder` 是單檔 HTML、原生 JS，**不要引入任何框架或 CDN**。
- `4_db_viewer` 前端不用 Pinia、不用 UI 元件庫 —— 三個檢視、唯讀資料，
  composables + 手刻 CSS 就夠。

### 範例
```
❌ 錯誤：為了讀 .env，建立 Factory Pattern + Strategy Pattern
✅ 正確：直接讀檔案、切 KEY=VALUE，用一個 dict 就好（見 bpm_kb/config.py）
```

---

## 3. 外科手術式修改

### 規則
- **只改必須改的地方**。不要順手「整理」、「重構」或「優化」不相關的程式碼。
- 不要改動現有的程式碼格式（縮排、空行、引號風格），除非那就是你的任務。
- 不要重新命名你沒被要求改的變數或函式。
- 每次修改都應該能用一句話解釋為什麼改。

### 範例
```
❌ 錯誤：修 bug 的同時，把整個檔案的 % 格式化改成 f-string，並重排 import
✅ 正確：只修改造成 bug 的那 3 行，其他一字不動
```

---

## 4. 目標導向執行

### 規則
- **先定義成功標準**：在開始之前，明確說出「做到什麼程度算完成」。
- 自己迭代直到達成目標，不要每做一步就停下來問。
- 如果遇到阻塞（缺少資訊、權限不足），才停下來回報。
- 完成時，簡要說明做了什麼、驗證了什麼。

### 本專案的驗證方式
| 改動範圍 | 必須跑的驗證 |
|:---|:---|
| `1_xml_tool/core/` | `cd 2_web_builder && node test_core.mjs`（62 項，JS 端對同一批範例檔交叉驗證） |
| `2_web_builder/index.html` | 同上 —— 測試會抽出 `CORE START/END` 區塊 |
| `3_db_explorer/bpm_kb/` | `python bpm_kb_tool.py check` 與 `pull`，比對 `out/*.json` |
| `4_db_viewer/backend/` | `pytest`，以及 `/docs` 能開、端點回得出 Pydantic 結構 |

### 範例
```
❌ 錯誤：「我已經寫好了 forms 端點，你要不要看一下再繼續？」
✅ 正確：「我完成了 forms 與 processes 兩組端點，已確認回應結構符合
    PLAN.md 第 4.1 節的 Pydantic 模型，只回傳 RELEASED 版本，
    並補上 orphaned 元件的標記。test_service.py 8 項通過。」
```

---

## 5. 尊重既有風格

### 規則
- **遵循現有程式碼的命名規範、寫法與慣例**，不要悄悄引入自己的風格。
- 新增程式碼前，先看同目錄下的現有檔案，學習它的風格。
- 保持一致性比「更好的寫法」更重要。

### 本專案慣例

**Python（`1_xml_tool`、`3_db_explorer`、`4_db_viewer/backend`）**

| 項目 | 規範 |
|:---|:---|
| 檔頭 | `# -*- coding: utf-8 -*-` |
| 命名 | 函式/變數 `snake_case`，類別 `PascalCase`，常數 `UPPER_CASE`，私有 `_prefix` |
| 字串格式化 | `%` 運算子（現有程式碼一致如此，**不要改成 f-string**） |
| 引號 | 單引號為主 |
| 類別宣告 | `class Foo(object):` |
| 型別註記 | 現有程式碼一律不寫。**例外**：`4_db_viewer` 的 Pydantic 模型必須寫（框架需要） |
| docstring | 繁體中文，說明「為什麼」而非「做什麼」 |
| 非同步 | 現有程式碼全為同步。FastAPI 端點若無 I/O 等待需求，用 `def` 即可 |

**前端**

| 項目 | 規範 |
|:---|:---|
| `2_web_builder` | 原生 JS，單一 HTML 檔，無框架、無 CDN、無建置步驟 |
| `4_db_viewer/frontend` | Vue 3 Composition API (`<script setup>`) + TypeScript + Vite |
| 樣式 | **手刻 CSS，不用 Tailwind、不用 UI 元件庫**（內網不保證連得到 CDN） |
| 狀態管理 | composables，不用 Pinia |
| 型別 | `src/api/types.ts` 由後端 OpenAPI 產生，**不可手改** |

**API（`4_db_viewer`）**

| 項目 | 規範 |
|:---|:---|
| 路徑 | `/api/{資源}/{識別碼}`，全小寫，多字用底線（與 Python 命名一致） |
| 方法 | **只有 GET**。本專案唯讀，不提供任何寫入端點 |
| 資料契約 | Pydantic 模型是唯一真實來源，前端型別由它產生 |

**資料庫**

| 項目 | 規範 |
|:---|:---|
| 系統 | SQL Server（測試區 `10.10.130.191` / `NaNa`） |
| 連線 | 一律經由 `bpm_kb.db.Database`，`readonly=True` |
| 查詢 | 一律參數化（`?` 佔位符），**絕不字串拼接使用者輸入** |
| ORM | 無。鼎新的 schema 是 OJB 產生的，硬套 ORM 只會製造麻煩 |

### 範例
```
❌ 錯誤：現有程式碼用 '%s' % x，你卻寫 f'{x}'
❌ 錯誤：現有 docstring 是繁體中文，你卻寫英文
✅ 正確：看到 list_forms() 就寫 list_processes()，保持風格一致
```

---

## 6. 失敗要明確說

### 規則
- **失敗就說失敗**，不能把「靜默跳過」包裝成「任務完成」。
- 如果某個步驟做不到、某個 API 回傳錯誤、某段程式碼無法通過測試，必須明確告知。
- 不要用 `try/except: pass` 吞掉錯誤。
- 不要刪掉失敗的測試案例來讓測試「通過」。
- **不要為了讓畫面好看而編造資料**。查不到就顯示查不到。

### 本專案的具體要求
- 權限清單裡有、但表單定義中不存在的元件（`orphaned`），必須標示出來。
  那代表流程版本與表單版本脫節，是真實問題，不可靜默忽略。
- 探索資料庫時若某欄位型別無法轉換而略過，要在結果中說明略過了什麼。
- 回報資料時附上取樣範圍（例如「取樣 4000 筆」），不要把樣本說成全體。

### 範例
```
❌ 錯誤：「已完成流程萃取」（實際上 5 支流程有 2 支解析失敗但沒提）
❌ 錯誤：靜默 catch 所有 exception，回傳空清單假裝成功
✅ 正確：「流程萃取完成 3/5。quickDevTestProcessImport v1、v2 的
    formFieldAccessDefinitionOID 為空，代表這兩版尚未設定欄位權限，
    不是解析失敗。」
```

---

## 7. 本專案的領域知識（動手前必讀）

### 7.1 表單與流程的存法完全不同

這是最容易踩雷的一點：

| | 存放方式 |
|:---|:---|
| **表單** | 整份 XML 存一格 —— `FormDefinition.defSerialize` |
| **流程** | 拆進關聯表 —— `ProcessDefinition.bpmXML` **只有畫布座標，不含邏輯** |

流程邏輯要靠 `containerOID = ProcessDefinition.OID` 把
`ActivityDefinition` / `TransitionDefinition` / `ParticipantDefinition` /
`FormFieldAccessDefinition` 撈齊才組得回來（見 `bpm_kb/process_graph.py`）。

**匯出的 `.bpmn` 檔在資料庫裡沒有對應欄位** —— 它是設計師重新序列化的產物。

#### 「這支流程用哪張表單」有兩個來源，只查一個會漏

資料表裡**沒有任何一欄記錄流程與表單的綁定關係**，要從兩處還原：

| 來源 | 位置 | 可信度 |
|:---|:---|:---|
| 主來源 | `FormFieldAccessDefinition.formFieldAccessControl` 的第一層子標籤 | 高，直接決定執行期欄位權限 |
| 次來源 | `ProcessPackage.subjectTemplet` 的 `<#表單ID~~欄位ID>` 語法 | 中，複製流程時會被一起帶走 |

**主來源的盲點**：`formFieldAccessControl` 只有在「該關卡設定過欄位權限」時才有值。
關卡沿用表單預設權限時這欄是 NULL，表單 ID 完全不落地。
2026-08-21 盤點 742 支最新 `RELEASED` 流程，有 87 支所有關卡都是 NULL ——
其中 49 支靠主旨範本救回來，剩 38 支兩邊都查不到
（31 支是沒掛公司別後綴的 `TIPTOPPROCESSPKG_*` 原廠範本，表單在 ERP 端）。

**查不到不等於沒有表單**。例如 `Companycars_Application_solar_`（碩禾公務車預約單）
四個關卡的 `formFieldAccessDefinitionOID` 都有值、`formFieldAccessControl` 全是 NULL，
但表單 `Company_cars_Application_Solar` 確實存在。

兩來源不一致的有 47 支（如 `TIPTOPPROCESSPKG_apyt104_*` 請假單的欄位權限指向
`axmt410` 一般訂單維護作業）。**不要自行挑一個當答案**，兩邊都是合法設定，
要標記出來給人工確認。

需要這份關聯時跑 `3_db_explorer/form_process_map.py`，不要重寫查詢。
已驗證走不通的路（`FormType`、`NoCmDocument`、`boundViewInformationOID`、
`ProcessInstance.contextOID`、流程與表單同名猜測等 8 條）記在
`3_db_explorer/out/鼎新BPM_表單流程關聯.md` 第 4.5 節，不要重複掃。

### 7.2 XML 回寫必須位元組級無損

`1_xml_tool/core/xml_utils.py` 用字串區間定位做編輯，不建 DOM。
理由是鼎新的 XML 帶有 XStream 的 `id` 參照與特定的空白格式，
任何重新序列化都會破壞它、導致匯入失敗。

改動這一層時，`node test_core.mjs` 的「回寫位元組不變」測試是硬性門檻。

### 7.3 權限值只有三種

資料庫實測（取樣 4000 筆 `FormFieldAccessDefinition`）：

| 值 | 佔比 |
|:---|:---|
| `ENABLED` | ~98% |
| `INVISIBLE` | ~1.3% |
| `FULL_CONTROL` | ~0.3% |
| （未列出） | 該關卡未設定，沿用表單預設 |

**不要自行發明 `READ_ONLY`、`HIDDEN` 之類的值。**

### 7.4 版本語意

- 表單：`version` 遞增，`containerOID` 是跨版本不變的邏輯身分
- 流程：版本在 `RedefinableHeader.version`，不在 `ProcessPackage` 上
- `objectVersion` 是 OJB 的樂觀鎖計數器，**與業務版本無關**
- `publicationStatus`：`RELEASED`（已發佈）/ `UNDER_REVISION`（修訂中）

### 7.5 不要重寫 SQL

`bpm_kb` 的關聯路徑是實測驗證過的。需要資料時 import 它的函式，
不要另外寫一套查詢 —— 兩份實作一定會漂移。

---

## 8. 安全與資料處理

- **資料庫一律唯讀**。任何 INSERT / UPDATE / DELETE / DDL 都不被允許，
  即使被要求也要先確認並說明風險。
- `.env` 含實際帳密，**不進版控、不輸出到日誌、不寫進 API 回應**。
  需要顯示連線資訊時用 `config.describe()`（它不吐密碼）。
- `samples/` 內是公司實際表單資料，已列入 `.gitignore`，不要改動這個設定。
- `4_db_viewer` 後端預設只綁 `127.0.0.1`，要對外開放需明確指示。

### 8.1 BPM SOAP API（`5_ws_explorer`）的操作邊界

「資料庫唯讀」這條規則**不涵蓋** SOAP 呼叫 —— 走 API 開單、簽核、作廢，
資料庫一樣會被改，只是繞過了 SQL。因此另立一組邊界：

| 對象 | 允許範圍 |
|:---|:---|
| **191 測試區**（`10.10.130.191:8080`） | 可自由呼叫，含開單、簽核等有副作用的方法 |
| **190 正式區**（`10.10.130.190:9090`） | **一律不連**，連唯讀查詢都不行 |
| 測試區資料庫 | 不可刪除既有資料。API 產生的新單可以留著，不必清 |

`probe_api.py` 已把這條邊界寫進程式：唯讀方法自動跑，有副作用的方法必須
`--method` 指名並加 `--allow-write`，`--endpoint` 指向 190 直接拒絕執行。
**不要為了方便把預設值改成整批寫入。**

呼叫 API 時另外要記得的三件事（完整說明見
`5_ws_explorer/docs/WorkflowService_API手冊.md`）：

- **回傳的 `string` 幾乎都不是純字串**，而是 XStream 序列化的 Java 物件、
  屬性式 XML 或逗號分隔清單。WSDL 的型別看不出來，要以實測樣本為準。
- **有些方法把例外包在回傳字串裡**（HTTP 200 + `<NotFoundException>`），
  只判斷有無丟例外會把錯誤當資料收下。
- **`invokeProcess` 不驗證表單欄位 id**，錯的欄位靜默寫入，
  之後 `fetchUniFormatFormInstance*` 讀取時才炸。
  組 `pFormFieldValue` 前先用 `getFormFieldTemplate` 對過欄位。

---

## 9. 回應規範

- 一律使用**繁體中文**回應。
- 程式碼中的**識別字（變數、函式、類別名）使用英文**；
  **註解與 docstring 使用繁體中文**（與現有程式碼一致）。
- 說明變更時優先列出：**實際修改的檔案** → **驗證方式與結果** → **尚未完成事項**。
- 引用檔案時附上路徑，必要時附行號（例如 `bpm_kb/process_graph.py:88`）。
- 提供指令時放在獨立的 bash 程式碼區塊，一個區塊一個指令。
