# 鼎新 BPM 快速開發工具集 —— 專案地圖

四個各自獨立、但共用同一套解析核心的工具，對應 BPM 開發的四個階段：
**改造既有檔案 → 設定權限 → 理解線上現況 → 隨時查閱與快速調整**，
外加一個獨立的 ⑤ `5_ws_explorer`，記錄 BPM 對外的 SOAP API 清單。

> **資料庫預設一律唯讀。** 全工具集只有一個地方會寫資料庫
> （`4_db_viewer/backend/app/writer.py`），且預設關閉、正式區永久禁寫。
> 詳見下方「安全邊界」。

```
BPM快速開發/
├── README.md              ← 本檔（專案地圖）
├── AGENTS.md              ← AI agent 開發規範（規範本體）
├── CLAUDE.md              ← 指向 AGENTS.md
├── samples/               ← 共用範例檔（.form / .bpmn，不進版控）
│
├── 1_xml_tool/            ① 萃取表單與流程
│   ├── PRD.md
│   ├── bpm_tool.py            終端互動主程式
│   └── core/                  ★ 解析核心，1／3／4 共用，2 有對應的 JS 實作
│       ├── xml_utils.py           XML 區塊定位與無損編輯
│       ├── form_handler.py        .form 萃取／回寫
│       └── bpmn_handler.py        .bpmn 萃取／回寫
│
├── 2_web_builder/         ② 建立新的表單與流程
│   ├── PRD.md
│   ├── index.html             單檔網頁工具，開啟即用
│   └── test_core.mjs          用真實範例檔驗證解析與位元組還原
│
├── 3_db_explorer/         ③ 查詢線上結構與說明
│   ├── bpm_kb/                資料庫萃取模組
│   ├── bpm_kb_tool.py         命令列進入點
│   ├── .env.example           連線設定範本
│   ├── docs/
│   │   ├── BPM_知識重點.md        ★ 自動產生的結構說明
│   │   └── schema/                資料表快照
│   └── out/                   撈下來的 .form / .bpmn / .json
│
├── 4_db_viewer/           ④ 線上結構檢視器 + 權限快速開發
│   ├── PLAN.md                專案計劃書（含寫入可行性實測記錄）
│   ├── README.md              使用說明
│   ├── backend/               FastAPI，沿用 3 的關聯邏輯
│   │   ├── app/writer.py          ★ 全工具集唯一的寫入路徑
│   │   └── backups/              寫入前的自動備份與稽核紀錄（不進版控）
│   └── frontend/              Vue 3 + Vite
│
└── 5_ws_explorer/         ⑤ BPM SOAP API 擷取與實測
    ├── README.md              使用說明與操作邊界
    ├── backend/               FastAPI 後端（提供 API 檢視與實測代理）
    ├── frontend/              Vue 3 + Vite 前端（手冊檢視與即時實測工作台）
    ├── wsdl_dump.py           抓 WSDL → 方法與參數清單
    ├── ws_client.py           手刻 rpc/encoded SOAP 客戶端
    ├── probe_api.py           對 191 測試區實測（唯讀方法才自動跑）
    ├── build_manual.py        合成 API 手冊
    ├── seeds.json             實測用參數值（人維護）
    ├── notes.json             ★ 各方法的語意註記（人維護）
    ├── docs/
    │   └── WorkflowService_API手冊.md   主產出
    └── out/                   WSDL 原檔、API 清單、實測結果與回傳樣本
```

---

## ① 1_xml_tool —— 萃取表單與流程

把鼎新匯出的 `.form` / `.bpmn` 拆成好讀的 JSON，改完 ID 再無損寫回。
用於批次套用命名規範，不必手工在幾十萬字的 XML 裡找替換。

```bash
cd 1_xml_tool
python bpm_tool.py                    # 互動選單
python bpm_tool.py export <檔案>       # 直接匯出 JSON
python bpm_tool.py write <JSON> [XML]  # 直接回寫
```

待處理的檔案放 `samples/`，產出為同目錄的 `已完成_<檔名>`。
回寫時會連動更新 `rwdLayout` 版面參照、`script` 內的表格事件函式，
以及 `formFieldAccessControl` 與郵件樣板中的欄位參照。

詳見 [1_xml_tool/PRD.md](1_xml_tool/PRD.md)。

## ② 2_web_builder —— 建立新的表單與流程

純本機單檔網頁，不需伺服器也不需安裝環境，開啟 `index.html` 即可用。
主要解決三個痛點：`formFieldAccessControl` 是二次逃脫 XML 難以手寫、
`.bpmn` 只有元件 ID 沒有中文名、以及看不到跨關卡的權限全貌。

```bash
cd 2_web_builder
start index.html          # 直接開啟
node test_core.mjs        # 跑回歸測試（62 項）
```

`index.html` 內 `// ==== CORE START ====` 到 `CORE END` 之間是解析核心，
測試檔會把它抽出來單獨驗證，確保「載入 → 修改 → 匯出」位元組層級可還原。

詳見 [2_web_builder/PRD.md](2_web_builder/PRD.md)。

## ③ 3_db_explorer —— 查詢線上結構與說明

直接連 BPM 資料庫（唯讀），把線上的表單定義與流程邏輯撈出來，
產生結構化 JSON 與一份重點文件，讓 AI 或新進人員不必開設計師介面就看懂一支流程。

```bash
cd 3_db_explorer
pip install -r requirements.txt
cp .env.example .env      # 填入連線帳密

python bpm_kb_tool.py check      # 測試連線
python bpm_kb_tool.py probe      # 探索資料表結構
python bpm_kb_tool.py pull       # 撈定義、組流程圖、產生文件
```

預設只看近 7 天匯入的版本（`--days=N` / `--all` / `--latest` 可調整），
因為鼎新改版後舊單的結構未必相同。

產出的 [3_db_explorer/docs/BPM_知識重點.md](3_db_explorer/docs/BPM_知識重點.md)
是這個專案的主要交付物，詳見 [3_db_explorer/bpm_kb/README.md](3_db_explorer/bpm_kb/README.md)。

## ④ 4_db_viewer —— 線上結構檢視器 + 權限快速開發

把 `3_db_explorer` 撈到的資料做成**前後端分離的網頁應用**：表單的元件
id／name／type，流程的關卡 id／name 與按鈕權限，並提供關卡 × 元件的權限矩陣。

```bash
cd 4_db_viewer/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000     # 唯讀模式
```

前端建置過（`cd frontend && npm install && npm run build`）之後，
只需跑 uvicorn 一個服務，開 <http://127.0.0.1:8000> 即可。

**三個檢視**：表單元件清單、流程關卡與按鈕權限、關卡 × 元件權限矩陣。
矩陣支援篩選元件、表頭排序（三態：升冪 → 降冪 → 表單原始順序）、
匯出目前檢視為 CSV。

**主機切換**：標題列下拉可在 191 測試區與 190 正式區之間切換，
主機是每個請求的參數（後端不存狀態），兩台快取各自獨立。
切到正式區會顯示紅色標記並自動退回唯讀。

**權限快速開發（選用，預設關閉）**：

```bash
BPM_VIEWER_ENABLE_WRITE=1 BPM_VIEWER_WRITABLE_PROCESSES=流程ID python -m uvicorn app.main:app --port 8000
```

開啟後矩陣頁多出「編輯權限」，可直接改按鈕與欄位權限並寫回資料庫，
省掉開設計師逐格點選的來回。改動先進 pending 區、預覽差異、確認才套用，
套用後可一鍵還原。**只改權限值，不碰任何結構。**

詳見 [4_db_viewer/README.md](4_db_viewer/README.md) 與
[PLAN.md](4_db_viewer/PLAN.md)（含寫入可行性的實測記錄）。

---

## ⑤ 5_ws_explorer —— BPM SOAP API 擷取與實測

前四個工具都走資料庫與 XML 檔案，這一個走**對外介面**：NaNaWeb 的
`WorkflowService`（Apache Axis 1.3、`rpc`/`encoded`、65 支方法）。

```bash
cd 5_ws_explorer
python wsdl_dump.py && python probe_api.py && python build_manual.py
```

抓 WSDL → 對 191 測試區實測 → 合成
[API 手冊](5_ws_explorer/docs/WorkflowService_API手冊.md)。
語意註記寫在 `notes.json`，與程式分離；手冊自動產生，不要手改。

**進度**：65 支中 29 支實測成功並留下回傳樣本，39 支已寫下用途與參數語意，
其餘多為有副作用的方法（開單、簽核、作廢），需要可拋棄的測試單才能驗。

**操作邊界**：191 測試區可自由呼叫；**190 正式區一律不連**
（`probe_api.py` 會直接拒絕）。唯讀方法自動跑，有副作用的方法必須指名。

WSDL 型別在這裡幫助有限 —— 41 支宣告回傳 `string`，實際塞的是 XStream
序列化的 Java 物件。這類只有實測才問得出來的事都記在手冊的「呼叫前必讀」，
包含一個會延後爆炸的地雷：`invokeProcess` 不驗證表單欄位 id。


---

## 四者的關係

```
        鼎新 BPM 設計師                        BPM 資料庫
              │ 匯出                                │ 唯讀連線
              ↓                                     ↓
        samples/*.form                        3_db_explorer
        samples/*.bpmn                     （撈定義、組流程圖）
              │                                     │
      ┌───────┴───────┐                             │
      ↓               ↓                             │
  1_xml_tool     2_web_builder                      │
 （改 ID）      （設權限、建新單）                      │
      │               │                             │
      └───────┬───────┘                             │
              ↓                                     ↓
        改好的 XML ──匯入──→ 鼎新 BPM ──→ docs/BPM_知識重點.md
                                              （驗證結果、留下說明）
                                                    │
                                                    ↓
                                              4_db_viewer
                                          （網頁瀏覽 + 權限微調）
                                                    ╎
                                        只有權限值可直接寫回資料庫
                                        （預設關閉，正式區永久禁寫）
```

`1_xml_tool/core/` 是共用的解析核心：`3_db_explorer` 直接 import 它來解析
撈下來的 XML，`4_db_viewer` 再經由 `bpm_kb` 間接使用同一套；
`2_web_builder` 則是它的 JavaScript 對應實作（邏輯一致，
以 `test_core.mjs` 對同一批範例檔交叉驗證）。

**分工界線**：結構性變更（加減元件、改關卡、改流程）走 ②，
純權限值的微調才走 ④。這條線要守住，否則版本控制會失控。

---

## 資料模型速查

理解這套系統最關鍵的一點：**表單與流程的存法完全不同**。

| | 存放方式 |
| --- | --- |
| **表單** | 整份 XML 存一格 —— `FormDefinition.defSerialize` |
| **流程** | 拆進關聯表 —— `ProcessDefinition.bpmXML` 只有畫布座標，不含邏輯 |

```
表單
  FormDefinition.defSerialize          .form 本體
                .script / rwdLayout    JS 與版面，另外存
                .containerOID          表單的邏輯身分，各版本共用
                .version / publicationStatus / validFrom / validTo

流程
  ProcessPackage                       一個版本一筆
   ├─ headerOID            → ProcessPackageHeader    createdTime
   ├─ redefinableHeaderOID → RedefinableHeader       version / publicationStatus
   └─ OID → ProcessPackage_ProcessDef → ProcessDefinition
                                          OID 即以下各表的 containerOID
        ActivityDefinition               關卡
         └─ formFieldAccessDefinitionOID → FormFieldAccessDefinition
                                            formFieldAccessControl = 欄位權限
        TransitionDefinition             連線 from → to
        ParticipantDefinition            執行者
```

匯出的 `.bpmn` 檔是設計師把這些關聯表重新序列化的結果 ——
資料庫裡沒有任何一個欄位長得跟它一樣。

**表單與流程之間沒有外鍵**，關聯寫在 `formFieldAccessControl` 裡：
每個關卡指定一張表單，並逐一列出該關卡對各欄位的權限。
這就是同一張表單在不同簽核關卡呈現不同樣貌的機制。

### 權限值（資料庫實測 20,000 筆 + 設計師 UI 對照）

| 資料庫存的值 | 設計師 UI | 佔比 |
| --- | --- | --- |
| `ENABLED` | 可編輯(Enable) | ~98.2% |
| `INVISIBLE` | 隱藏(Invisible) | ~1.5% |
| `FULL_CONTROL` | （UI 未對照到） | ~0.2% |
| **未列出** | **唯讀(Disable)** | — |

資料庫只存三種值。**要把元件設成唯讀，作法是把它從權限字串中移除**，
不是寫入某個值。`INVALIDITY`（失效）在取樣中從未出現，格式未知。

### 一個會出事的地雷

權限定義列**會被多個關卡共用**。全庫掃描發現：

```
1def277bd04a10048563bc0546718357  被 24,765 個關卡引用
329200f5de1510048afb1d2d9212f85e  被 24,707 個關卡引用
```

改一筆就是改上萬個關卡。任何寫入路徑都必須先檢查
`SELECT COUNT(*) FROM ActivityDefinition WHERE formFieldAccessDefinitionOID = ?`，
不是 1 就拒絕 —— `4_db_viewer` 已內建這道檢查。

---

## 安全邊界

| 元件 | 資料庫存取 |
| --- | --- |
| `bpm_kb.db.Database`（1／3／4 共用） | **`readonly=True`**，永遠唯讀 |
| `3_db_explorer` CLI 的 `sql` 指令 | 只接受 `SELECT` / `WITH` |
| `4_db_viewer` 唯讀端點 | 全為 `GET`，參數化查詢，不接受 SQL 片段 |
| `4_db_viewer/backend/app/writer.py` | **唯一的寫入路徑**，另開連線，不與唯讀共用 |

寫入路徑的十道防護（共用列偵測、預設關閉、流程白名單、主機白名單、
強制備份、稽核紀錄、兩段式 preview／apply、值白名單、rowcount 驗證、
寫後回讀）詳見 [4_db_viewer/README.md](4_db_viewer/README.md)。

**已知風險**：這條路徑繞過 BPM 的版本控制，設計師 UI 看不出改過，
且 `objectVersion` 不遞增 —— 日後有人從設計師存檔會靜默覆蓋。
測試區練手沒問題，正式區預設就寫不進去。

`.env`（連線帳密）、`samples/` 內的實際表單檔、
`4_db_viewer/backend/backups/` 都已列入 `.gitignore`。

---

## 環境需求

| 專案 | 需求 |
| --- | --- |
| 1_xml_tool | Python 3.x，無第三方套件 |
| 2_web_builder | 瀏覽器即可；跑測試需 Node.js |
| 3_db_explorer | Python 3.x + `pyodbc`，以及 SQL Server ODBC 驅動 |
| 4_db_viewer | 後端 Python 3.x + FastAPI（需 3_db_explorer 的環境）；前端 Node.js + Vite |
| 5_ws_explorer | 後端 Python 3.x + FastAPI；前端 Node.js + Vite |

已驗證組合：Python 3.14.3、FastAPI 0.141.1、Pydantic 2.13.4、
Node v24.14.0、npm 11.12.0、ODBC Driver 18 for SQL Server、SQL Server 2019。

## 測試

| 專案 | 指令 | 目前 |
| --- | --- | --- |
| 1_xml_tool ／ 2_web_builder | `cd 2_web_builder && node test_core.mjs` | 62 項通過 |
| 4_db_viewer 後端 | `cd 4_db_viewer/backend && python -m pytest tests -q` | 33 通過、2 跳過 |
| 4_db_viewer 前端 | `cd 4_db_viewer/frontend && npx vue-tsc --noEmit` | 無錯誤 |
| 5_ws_explorer 前端 | `cd 5_ws_explorer/frontend && npx vue-tsc --noEmit` | 無錯誤 |

那 2 個跳過的是**真的會寫資料庫**的整合測試，需三個環境變數同時設齊才會執行；
跳過時會說明原因，不會假裝通過。

改動 `1_xml_tool/core/` 一定要跑 `node test_core.mjs` ——
它會用真實範例檔驗證「載入 → 修改 → 匯出」位元組層級可還原。
