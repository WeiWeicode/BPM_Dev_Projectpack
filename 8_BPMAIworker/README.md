# 8_BPMAIworker —— AI 產生鼎新 BPM 表單與流程

> 狀態：規格文件 + 第一組可執行的組裝工具。
> 已產出第一個實測用專案 `samples/AI設計的流程測試/`
> （靜態檢查與反解對比全過，**尚未匯入鼎新設計師實測**）。

---

## 1. 這個工具要解決什麼

①～⑦ 都是**在既有檔案／既有線上資料上工作**：改 ID、設權限、查結構、匯出稽核。
唯獨「從一句需求做出一張新表單與一支新流程」這件事，目前仍是純手工——
在設計師裡逐格拉元件、逐關卡點權限、再手寫腳本。

`8_BPMAIworker` 的目標是把這段自動化：

```
人類的需求描述  →  AI  →  可直接匯入鼎新設計師的 .form + .bpmn + .js
```

**參考基準**：`samples/太陽能ECRECN/`（已上線的實際流程與表單）與
`samples/快速開發測試/`（涵蓋 27 種元件型別的教材檔）。
前者證明「什麼是合格的產出」，後者是元件型別的完整字典。

---

## 2. 最重要的一個設計決定：AI 不直接寫 XML

這不是保守，是三個實測出來的硬限制決定的：

| 限制 | 實測數據（`原檔案-quickDevTestForm.form`／`原檔案-測試快速開發.bpmn`） |
|:---|:---|
| **XStream 連號 id** | `.form` 內 `id="1"` ～ `id="747"` **嚴格連號、無跳號**，另有 46 處 `reference="8"` 指回其中一個節點。插入或刪除任何一個元件，其後**全部**編號與參照都要重算。 |
| **OID 是 32 碼且不可重複** | `.bpmn` 內 76 個 `<OID>` 全數互異，其中 74 個共用同一組 24 碼後綴 `f9e21004851cac97a977dbbf`，前 8 碼遞增。這是伺服器端的識別碼配置規則，不是隨機字串。 |
| **權限是二次逃脫 XML** | `<formFieldAccessControl>` 的內容是被逃脫過的 XML 字串：`&lt;FormFieldAccessControl&gt;&lt;表單ID&gt;&lt;欄位ID&gt;ENABLED&lt;/...` 。 |

再加上單一 `ActivityDefinition` 就有 **67 個直屬子標籤、約 9.8 KB**，
`InputElementDefinition` 有 40 個、`SelectElementDefinition` 有 29 個——
其中絕大多數是與業務無關的樣板值。

**要 LLM 逐字產生這些內容，必然在某一格出錯，而且錯了不會報錯，是匯入時才炸。**

所以架構是：

```
需求描述 ──AI──▶ IR（意圖規格 JSON）──確定性組裝器──▶ .form / .bpmn / .js
                      ↑ AI 只負責這一層          ↑ 編號、OID、逃脫、樣板由程式負責
```

AI 決定「有哪些欄位、叫什麼、在第幾列、哪個關卡看得到」；
程式負責「連號、OID、逃脫、67 個樣板標籤」。兩邊各做自己不會出錯的事。

---

## 3. 與其他子專案的分工

| 需求 | 走哪個 |
|:---|:---|
| 從零產生新表單／新流程 | **⑧ 本工具** |
| 改既有檔案的元件 ID、關卡 ID | ① `1_xml_tool` |
| 視覺化調既有檔案的欄位權限 | ② `2_web_builder` |
| 查線上已有哪些表單／流程可參考 | ③ `3_db_explorer` |
| 產出後拿去測試區實際開單驗證 | ⑤ `5_ws_explorer`（**只打 191 測試區**） |

⑧ 會**直接沿用** `1_xml_tool/core/` 的解析核心來做產出物的自我驗證
（產生 → 用 `form_handler.extract()` 反解 → 比對是否等於當初的 IR），
不另寫一套解析。

---

## 4. 規劃中的目錄結構

```text
8_BPMAIworker/
├── README.md                    ← 本檔
├── PLAN.md                      ← 架構、管線、里程碑、未驗證項目
└── docs/
    ├── AI產生規格_IR.md          ★ AI 唯一的輸出格式（意圖規格）
    ├── 表單生成手冊.md            .form 的骨架、元件型別、版面、編號規則
    ├── 流程生成手冊.md            .bpmn 的骨架、關卡、連線、權限、OID 規則
    ├── 表單腳本手冊.md            .js 的生命週期、全域變數、可用資源與禁忌
    └── 驗證與驗收.md              五層驗證管線與驗收標準
├── templates/                   ★ 新專案的基底
│   ├── README.md                範本清冊：裡面有什麼、缺什麼、複製時換掉哪幾格
│   └── 原始空白專案/             鼎新設計器直接匯出的空白專案（表單 0 元件、流程 4 關卡）
├── tools/                       ★ 目前實際可跑的組裝工具（Python，零第三方依賴）
│   ├── xstream_ref.py           XStream 相對參照解析與就地展開
│   ├── bpm_edit.py              共用編輯動作（定位／刪除／OID 重配／權限／重編號）
│   ├── new_project.py           ★ 從空白範本複製出一個新專案
│   ├── set_permissions.py       ★ 把關卡欄位權限寫進 .bpmn（可插入不存在的節點）
│   ├── build_form.py            以教材表單為底組出新的 .form
│   ├── build_bpmn.py            以教材流程為底組出新的 .bpmn
│   └── verify.py                靜態檢查 + 用 1_xml_tool 反解對比
（以下為 M2 之後才會出現）
├── ir/                          IR 的 JSON Schema 與範例
└── builder/                     由 IR 直接組裝（目前是寫死設定的 build_*.py）
```

### 兩條產出路線

| 路線 | 什麼時候用 | 入口 |
|:---|:---|:---|
| **從空白範本長出來** | 要做一支全新的流程 | `tools/new_project.py` → `tools/set_permissions.py` |
| **改造既有的教材檔** | 要一次拿到很多現成元件（表單元件庫） | `tools/build_form.py` / `tools/build_bpmn.py` |

空白範本的流程剛好就是 `開單人 → 直屬主管 → 結案`，
執行者也已經是 `PROCESS_REQUESTER` / `MANAGER`，所以新流程不必自己編執行者型別。
它唯一缺的是 `<formFieldAccessControl>`（關卡權限），那正是 `set_permissions.py` 要補的。

### tools/ 目前做得到什麼

| 能力 | 說明 |
|:---|:---|
| 展開 XStream 參照 | `.form` 的數字 `reference` 與 `.bpmn` 的 XPATH 相對 `reference` 都能解析並就地展開。**這是能安全增刪元件與關卡的前提** |
| 重編 XStream id | 展開參照後全檔重編 1…N，新增元件不會踩到連號問題 |
| 改 ID／中文名／權限 | 走 `1_xml_tool/core` 已有測試保護的 write_back |
| 刪關卡並改接連線 | 連同執行者、連線、流程圖節點一起處理 |
| 重配 OID | 全檔換成本專案自己的一組，避免與線上定義撞號 |
| 插入欄位權限 | 關卡只有 `formFieldAccessDefinition`、沒有 `formFieldAccessControl` 時，直接插一個進去 |
| 靜態檢查 | 連號、參照、版面一致性、圖形與關卡一致性、權限欄位是否真的存在 |

```bash
python 8_BPMAIworker/tools/new_project.py --name 採購申請單 --form-id PurchaseForm --process-id PurchaseProcess
```

```bash
python 8_BPMAIworker/tools/verify.py
```

---

## 5. 文件索引

| 文件 | 什麼時候看 |
|:---|:---|
| [PLAN.md](PLAN.md) | 想知道整體怎麼做、分幾期、哪些還沒驗證 |
| [docs/AI產生規格_IR.md](docs/AI產生規格_IR.md) | **AI 產生內容前必讀**，這是唯一該輸出的格式 |
| [docs/表單生成手冊.md](docs/表單生成手冊.md) | 要動 `.form` 結構時 |
| [docs/流程生成手冊.md](docs/流程生成手冊.md) | 要動 `.bpmn` 結構時 |
| [docs/表單腳本手冊.md](docs/表單腳本手冊.md) | 要產生表單 JavaScript 時 |
| [docs/驗證與驗收.md](docs/驗證與驗收.md) | 產出後要確認能不能用時 |

上層規範一律以 [AGENTS.md](../AGENTS.md) 為準，本目錄不重複。
