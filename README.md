# 鼎新 BPM 快速開發工具集 —— 專案地圖

四個各自獨立、但共用同一套解析核心的工具，對應 BPM 開發的四個階段：
**改造既有檔案 → 設定權限 → 理解線上現況 → 隨時查閱**。

```
BPM快速開發/
├── README.md              ← 本檔（專案地圖）
├── samples/               ← 共用範例檔（.form / .bpmn，不進版控）
│
├── 1_xml_tool/            ① 萃取表單與流程
│   ├── PRD.md
│   ├── bpm_tool.py            終端互動主程式
│   └── core/                  ★ 解析核心，三個專案共用
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
└── 4_db_viewer/           ④ 線上結構檢視器（規劃中）
    ├── PLAN.md                專案計劃書
    ├── backend/               FastAPI，沿用 3 的關聯邏輯
    └── frontend/              Vue 3 + Vite
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

## ④ 4_db_viewer —— 線上結構檢視器（規劃中）

把 `3_db_explorer` 撈到的資料做成**前後端分離的網頁應用**：表單的元件
id／name／type，流程的關卡 id／name 與按鈕權限，並提供關卡 × 元件的權限矩陣。

- 後端 FastAPI，直接 import `bpm_kb` 的關聯邏輯，唯讀連線、無寫入端點
- 前端 Vue 3 + Vite，型別由後端 OpenAPI 產生，契約只有一份
- **只呈現 RELEASED 版本**，與專案 ② 完全隔離，不提供任何回寫

詳見 [4_db_viewer/PLAN.md](4_db_viewer/PLAN.md)。

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
                                           （網頁瀏覽，唯讀）
```

`1_xml_tool/core/` 是共用的解析核心：`3_db_explorer` 直接 import 它來解析
撈下來的 XML，`2_web_builder` 則是它的 JavaScript 對應實作（邏輯一致，
以 `test_core.mjs` 對同一批範例檔交叉驗證）。

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
每個關卡指定一張表單，並逐一列出該關卡對各欄位的權限
（實測值為 `ENABLED` / `INVISIBLE` / `FULL_CONTROL`）。這就是同一張表單
在不同簽核關卡呈現不同樣貌的機制。

---

## 環境需求

| 專案 | 需求 |
| --- | --- |
| 1_xml_tool | Python 3.x，無第三方套件 |
| 2_web_builder | 瀏覽器即可；跑測試需 Node.js |
| 3_db_explorer | Python 3.x + `pyodbc`，以及 SQL Server ODBC 驅動 |
| 4_db_viewer | 後端 Python 3.x + FastAPI（需 3_db_explorer 的環境）；前端 Node.js + Vite |

`.env`（連線帳密）與 `samples/` 內的實際表單檔都已列入 `.gitignore`。
