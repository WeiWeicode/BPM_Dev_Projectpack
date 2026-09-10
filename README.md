# 鼎新 BPM 快速開發工具集 —— 專案地圖

八個各自獨立、但共用同一套解析核心與資料庫模組的工具，涵蓋 BPM 開發、API 整合、日常流程查詢與稽核調閱：
**改造既有檔案 → 設定權限 → 理解線上現況 → 隨時查閱與快速調整**，
外加 ⑤ `5_ws_explorer`（SOAP API 擷取與實測工作台）、⑥ `6_todo_viewer`（個人待辦與單據查詢器）
與 ⑦ `7_proc_export`（流程與表單匯出，供稽核調閱）、
⑧ `8_BPMAIworker`（AI 產生新表單與新流程，**組裝工具可跑，尚未匯入設計師實測**）；
以及 `BPM5892`（鼎新原廠 WildFly 核心程式的深層架構解構、Struts 路由、DWR 服務與 ERP 整合知識庫）。

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
│   └── core/                  ★ 解析核心，1／3／4／6 共用，2 有對應的 JS 實作
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
├── 5_ws_explorer/         ⑤ BPM SOAP API 擷取與實測
│   ├── README.md              使用說明與操作邊界
│   ├── backend/               FastAPI 後端（提供 API 檢視與實測代理）
│   ├── frontend/              Vue 3 + Vite 前端（手冊檢視與即時實測工作台）
│   ├── wsdl_dump.py           抓 WSDL → 方法與參數清單
│   ├── ws_client.py           手刻 rpc/encoded SOAP 客戶端
│   ├── probe_api.py           唯讀方法實測
│   ├── probe_write.py         有副作用方法的情境式實測（會開單、跑完自動收單）
│   ├── build_manual.py        合成 API 手冊
│   ├── seeds.json             實測用參數值（人維護）
│   ├── notes.json             ★ 各方法的語意註記（人維護）
│   ├── docs/
│   │   └── WorkflowService_API手冊.md   主產出
│   └── out/                   WSDL 原檔、API 清單、實測結果與回傳樣本
│
├── 6_todo_viewer/         ⑥ BPM 待辦與流程查詢器
│   ├── PLAN.md                計畫書與決策記錄
│   ├── README.md              使用說明與防雷手冊
│   ├── probe_todo.py          待辦狀態與深連結實測腳本
│   ├── docs/
│   │   └── 待辦狀態語意.md        ★ 待辦收件匣與狀態碼實測
│   ├── backend/               FastAPI（待辦/經辦/申請查詢 + 欄位中文名即時解析）
│   └── frontend/              Vue 3 + Vite（三頁籤清單 + 詳情抽屜 + BPM 深連結）
│
├── 7_proc_export/         ⑦ 流程與表單匯出（稽核調閱）
│   ├── README.md              使用說明、欄位名稱實測數據與狀態碼依據
│   ├── backend/               FastAPI（查單 + Excel 匯出，全唯讀）
│   │   └── app/excel.py       ★ 清單／內容／明細／簽核名單寫成同一個 Excel
│   └── frontend/              Vue 3 + Vite（流程清單 + 查詢 + 欄位挑選抽屜 + 明細面板）
│
├── 8_BPMAIworker/         ⑧ AI 產生表單與流程（工具可跑，L2／L3 待人工實測）
│   ├── README.md              定位、與 ①～⑦ 的分工、為何 AI 不直接寫 XML
│   ├── PLAN.md                管線、模組切分、里程碑與未驗證項目
│   ├── templates/             設計師匯出的空白專案，新專案一律從這裡複製
│   ├── tools/                 ★ 組裝工具（Python，零第三方依賴）
│   │   ├── new_project.py       從空白範本複製出新專案
│   │   ├── fetch_online.py      唯讀抓線上流程／表單／腳本當範本
│   │   ├── build_from_online.py 把線上舊表單重建成響應式新專案
│   │   ├── build_from_spec.py   ★ 由 AI 寫的 IR 直接組出 .form / .js / .bpmn
│   │   └── verify.py            靜態檢查 + 用 1_xml_tool 反解對比
│   └── docs/
│       ├── AI產生規格_IR.md    ★ AI 唯一的輸出格式（意圖規格 JSON）
│       ├── 表單生成手冊.md      .form 骨架、元件型別、版面與 XStream 編號規則
│       ├── 流程生成手冊.md      .bpmn 骨架、關卡、連線、權限逃脫與 OID 規則
│       ├── 表單腳本手冊.md      .js 生命週期、全域變數、可用資源與禁忌
│       ├── 線上抓取手冊.md      ★ 照著線上既有流程仿造的提示詞與唯讀邊界
│       ├── 從需求生成手冊.md    ★ 只有一張圖或一份欄位清單時的提示詞與命名規則
│       └── 驗證與驗收.md        五層驗證管線與各里程碑的驗收標準
│
└── BPM5892/                 鼎新原廠系統核心與解構知識庫
    ├── BPM系統地圖.md         ★ 系統入口、Struts 路由（68 模組 / 254 路由）與 DWR 清冊
    ├── BPM系統分析.md         技術棧盤點（WildFly 15/EJB 3/Struts 1.3）與部署單元架構
    ├── BPM_ERP整合介面.md     BPM ↔ ERP 雙向介面清冊（Call Out 87 方法 / Call In 介面）
    ├── BPM_表單腳本可用資源.md ★ 表單腳本可用資源（DWR 45 服務、預載 JS、CustomJsLib）
    └── wildfly-15.0.0.Final/  原廠伺服器部署本體（檔案極多，已列入 .gitignore，非必要勿讀）
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

**進度**：65 支方法全部都有用途與參數語意的記錄。實測執行成功 58 支
（唯讀 33、有副作用 25 —— 實際開單、簽收、轉派、跳關、取回重辦、作廢），
失敗 6 支原因均已查明，1 支（`importOrganizationData`）刻意不測。

**操作邊界**：191 測試區可自由呼叫；**190 正式區一律不連**（程式直接拒絕）。
`probe_write.py` 開出的單在跑完後全部作廢或終止，不留待辦。

WSDL 型別在這裡幫助有限 —— 41 支宣告回傳 `string`，實際塞的是 XStream
序列化的 Java 物件。這類只有實測才問得出來的事都記在手冊的「呼叫前必讀」，
包含兩個會延後爆炸的地雷：`invokeProcess` 不驗證表單欄位 id，
以及使用者 OID 必須取 `Users.OID` 而非 `Employee.OID`（兩者只差一個字元）。


---

## ⑥ 6_todo_viewer —— BPM 待辦與流程查詢器

輸入**員工編號或姓名**，查出這個人的待簽核、我申請的、我經辦過的三類單據，
點單號看表單內容（即時解析各版本欄位中文名稱）與簽核歷程，每筆都附深連結直接跳回 BPM ——
待簽核提供「簽核」（`PerformWorkFromMail`），三個分頁皆提供「追蹤」（`TraceProcessMain`）。

```bash
cd 6_todo_viewer/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8100
```

前端建置過（`cd frontend && npm install && npm run build`）後，
只需跑 uvicorn 一個服務，開 <http://127.0.0.1:8100> 即可（開發模式跑 `npm run dev`）。

**特色與防雷設計**：
- **待辦收件匣精準定位**：待辦關聯查詢 `LocalToDoWorkItem`（而非未完成時必為 NULL 的 `WorkItem.performerOID`）。
- **同人多帳號處理**：不同公司別為不同帳號，查詢一律回候選清單讓人明確挑選。
- **表單關聯防掉單**：`LocalRelevantData` 採單獨查詢並 `JOIN FormInstance`，避免多流程變數列造成隨機抓不到表單。
- **BPM 深連結跟著主機走**：依查詢來源（191 測試區／190 正式區）動態產生深連結，點擊即可直達 BPM。
- **欄位中文名即時解析**：經由 `FormDefinition.defSerialize` 解析當時版本的元件定義並快取，準確還原欄位中文名。

詳見 [6_todo_viewer/README.md](6_todo_viewer/README.md) 與 [PLAN.md](6_todo_viewer/PLAN.md)。

---

## ⑦ 7_proc_export —— 流程與表單匯出（稽核調閱）

挑一支流程 → 查單 → 看表單內容 → 把**清單／表單內容／簽核名單**匯成
單一 Excel 的不同 tab。三項可任選，表格控件的明細另開工作表（一列一筆）。

```bash
cd 7_proc_export/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8002
```

前端建置過（`cd frontend && npm install && npm run build`）後只需跑 uvicorn，
開 <http://127.0.0.1:8002>（開發模式跑 `npm run dev`，用 5176 埠）。

**特色與防雷設計**：
- **實例層的表單關聯**：`ProcessInstance.contextOID → LocalRelevantData → FormInstance`，
  每張單都問得到自己掛哪張表單，不需要用定義層那兩個會漏的來源去猜。
- **流程單號與表單單號分兩欄**：兩者是不同編號（`SHROT_00004620` vs `E071320320`），
  不能互相 join，也不能混成一個「單號」。
- **欄位名稱誠實標示**：舊表單的定義裡多半沒填標籤，查不到就顯示欄位 ID
  並用灰色斜體標出，另附「欄位對照」工作表。**刻意不用座標鄰近去猜** ——
  實測會把「部門代號」配成「部門名稱」，稽核文件上標錯比標 ID 更糟。
- **表格明細名稱可靠**：`ListItem` 的 `<caption>` 是設計師實填的欄位標題，實測 100% 有中文。
- **自訂欄位條件在 Python 端比對**：`fieldValues` 是 ntext、55 萬列，
  下 SQL `LIKE` 會全表掃描（實測 120 秒未回），故先用流程＋日期壓小候選再逐張解析；
  壓到掃描上限時畫面會明說只比對了部分單據。
- **日期區間必填、筆數有上限**：超過就擋下並要求縮小範圍，不會偷偷只匯前面幾筆。

詳見 [7_proc_export/README.md](7_proc_export/README.md)。

---

## ⑧ 8_BPMAIworker —— AI 產生表單與流程

①～⑦ 都是在既有檔案或既有線上資料上工作。唯獨「從一句需求做出一張新表單與一支新流程」
仍是純手工。⑧ 要把這段自動化：**需求描述 → AI → 可匯入設計師的 `.form` + `.bpmn` + `.js`**。

**目前狀態：三條產出路線的組裝工具都能跑，L1（反解對比）全過；
L2（匯入設計師）與 L3（實跑一張單）仍須人工，其中「從需求生成」這條尚未有人匯過。**

| 路線 | 手上有什麼 | 入口 |
|:---|:---|:---|
| 從空白範本長出來 | 只要一個空殼 | `tools/new_project.py` |
| 照著線上既有流程做 | 線上有一支可以照抄 | `tools/fetch_online.py` → `tools/build_from_online.py` |
| 從需求生成 | 一張截圖／一份欄位清單 | AI 寫 IR → `tools/build_from_spec.py` |

核心設計決定是 **AI 不直接產生 XML**，只產生一份「意圖規格（IR）」JSON，
再由確定性組裝器套樣板產出檔案。理由是三個實測出來的硬限制：
`.form` 的 XStream `id` 為 1…747 嚴格連號且有 46 處數字 `reference`、
`.bpmn` 的 32 碼 OID 全檔唯一且有固定配發規則、
欄位權限是二次逃脫的 XML——這三件事讓 LLM 逐字生成必然在某一格出錯，
而且錯了不會報錯，是匯入時才炸。

解析與自我驗證一律沿用 `1_xml_tool/core`，不另寫一套。
產出物要驗證時用 ⑤ 對 **191 測試區**；190 正式區一律不碰。

詳見 [8_BPMAIworker/README.md](8_BPMAIworker/README.md) 與
[PLAN.md](8_BPMAIworker/PLAN.md)；兩條需要 AI 參與的路線各有一份提示詞手冊：
[線上抓取手冊](8_BPMAIworker/docs/線上抓取手冊.md)、
[從需求生成手冊](8_BPMAIworker/docs/從需求生成手冊.md)。

---

## ⑨ BPM5892 —— 鼎新原廠系統核心與解構知識庫

鼎新 BPM（產品內部代號 **EFGP**，流程引擎代號 **NaNa**）跑在 **WildFly 15.0.0.Final** 上的原廠應用程式本體與深度解構。
為避免在龐大且未經混淆的 Java class、JSP、設定檔中大海撈針，本目錄已將底層架構精煉為四份系統地圖與規格清冊：

| 文件 | 核心內容與查閱指引 |
|:---|:---|
| [BPM系統地圖.md](BPM5892/BPM系統地圖.md) | **系統入口與 Struts 路由總覽**：整理 68 個 Struts 模組、254 條 URL 路由（含 PerformWorkItem 26 條核心路由）、`ActionServlet` 與 `hdnMethod` 分派機制、45 個 DWR 前後端直呼服務，以及 URL 組成規則。 |
| [BPM系統分析.md](BPM5892/BPM系統分析.md) | **技術棧與部署架構盤點**：分析 WildFly 15、Java EE/EJB 3、Struts 1.3、Quartz 排程、Castor/XPDL 流程模型等底層元件；記錄 65GB 歷史 log 清理歷程與 12 個部署單元（1.1 GB）解構。 |
| [BPM_ERP整合介面.md](BPM5892/BPM_ERP整合介面.md) | **BPM ↔ ERP 雙向介面清冊**：Call Out 87 個核心 ERP 方法（支援 TIPTOP、T100、SAP、易飛、Cosmos 等）、Call In SOAP Web Service（35 個白名單方法 + 143 個全開放方法），以及真實故障案例對策。 |
| [BPM_表單腳本可用資源.md](BPM5892/BPM_表單腳本可用資源.md) | **表單設計器腳本可用資源**：清點前端表單已預載的 28 個 JS 函式庫（免載即可用）、45 支 DWR 後端服務（866 個可直呼方法）、CustomJsLib 20 支共用庫與 OpenWin 4 大資料選擇器開窗函式。 |

> **特別注意**：`wildfly-15.0.0.Final/` 為原廠伺服器部署本體，檔案極多已列入 `.gitignore`。
> 日常開發、排查問題與查閱架構**優先閱讀上述 4 份提煉好的 Markdown 文件**，非必要不要逐檔讀取或掃描 WildFly 目錄。

---

## 各工具與模組的關係

```
        鼎新 BPM 設計師                        BPM 資料庫
              │ 匯出                                │ 唯讀連線
              ↓                                     ↓
        samples/*.form                        3_db_explorer
        samples/*.bpmn                     （撈定義、組流程圖）
              │                                     │
      ┌───────┴───────┐                             ├─────────────────┐
      ↓               ↓                             ↓                 ↓
  1_xml_tool     2_web_builder                 4_db_viewer       6_todo_viewer
 （改 ID）      （設權限、建新單）          （結構瀏覽+權限微調）  （個人待辦/單據查詢）
                                                                7_proc_export
                                                              （稽核清單/內容匯出）
      │               │                             ╎                 │
      └───────┬───────┘                 只有權限值可直接寫回資料庫    附深連結跳回 BPM
              ↓                         （預設關閉，正式區永久禁寫）          │
        改好的 XML ──匯入──→ 鼎新 BPM ──────────────────────────────────────┘
                                ▲
                                │ SOAP 呼叫
                                │
                          5_ws_explorer
                      （API 擷取、實測工作台）
                                │
                                └── 參照底層架構、路由、DWR 服務、ERP 介面與表單可用 JS ──┐
                                                                                         ↓
                                                                                   BPM5892/
                                                                            （原廠系統解構知識庫）
```

- `1_xml_tool/core/` 是共用的解析核心：`3_db_explorer` 直接 import 它來解析撈下來的 XML，`4_db_viewer`、`6_todo_viewer` 與 `7_proc_export` 亦透過 `bpm_kb` / `core` 解析表單定義與欄位中文名；`2_web_builder` 則是其 JavaScript 對應實作（以 `test_core.mjs` 交叉驗證）。
- **分工界線**：
  - 離線檔案結構性變更（改 ID、加減元件、改關卡、改流程）走 ①、②。
  - 線上定義查詢與文件萃取走 ③。
  - 線上結構與權限矩陣檢視、純權限值微調走 ④。
  - 外部系統整合與 SOAP WebService 呼叫、實測工作台走 ⑤。
  - 日常作業、待簽單據追蹤、個人申請/經辦歷史查閱與深連結跳轉走 ⑥。
  - 稽核調閱、跨關卡歷程與多頁籤 Excel 匯出走 ⑦。
  - 原廠底層架構、Struts 路由、DWR 服務、ERP 介面與表單腳本可用資源查閱走 `BPM5892/`。

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
| `bpm_kb.db.Database`（1／3／4／6／7 共用） | **`readonly=True`**，永遠唯讀 |
| `3_db_explorer` CLI 的 `sql` 指令 | 只接受 `SELECT` / `WITH` |
| `4_db_viewer` 唯讀端點 | 全為 `GET`，參數化查詢，不接受 SQL 片段 |
| `4_db_viewer/backend/app/writer.py` | **唯一的寫入路徑**，另開連線，不與唯讀共用 |
| `5_ws_explorer` | SOAP 呼叫，**190 正式區永久拒絕連線**；副作用方法需明確授權 |
| `6_todo_viewer` 查詢端點 | 全為 `GET`，永遠唯讀，純 SQL 查詢不呼叫 SOAP |
| `7_proc_export` 全部端點 | 永遠唯讀，無任何寫入路徑；`POST` 只用來傳結構化查詢條件 |

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
| 6_todo_viewer | 後端 Python 3.x + FastAPI（需 3_db_explorer 的環境）；前端 Node.js + Vite |
| 7_proc_export | 後端 Python 3.x + FastAPI + `openpyxl`（需 3_db_explorer 的環境）；前端 Node.js + Vite |

已驗證組合：Python 3.14.3、FastAPI 0.141.1、Pydantic 2.13.4、
Node v24.14.0、npm 11.12.0、ODBC Driver 18 for SQL Server、SQL Server 2019。

## 測試

| 專案 | 指令 | 目前 |
| --- | --- | --- |
| 1_xml_tool ／ 2_web_builder | `cd 2_web_builder && node test_core.mjs` | 62 項通過 |
| 4_db_viewer 後端 | `cd 4_db_viewer/backend && python -m pytest tests -q` | 33 通過、2 跳過 |
| 4_db_viewer 前端 | `cd 4_db_viewer/frontend && npx vue-tsc --noEmit` | 無錯誤 |
| 5_ws_explorer 後端 | `cd 5_ws_explorer/backend && python -m pytest tests -q` | 8 項通過 |
| 5_ws_explorer 前端 | `cd 5_ws_explorer/frontend && npx vue-tsc --noEmit` | 無錯誤 |
| 6_todo_viewer 後端 | `cd 6_todo_viewer/backend && python -m pytest tests -q` | 23 項（14 純邏輯通過、9 整合視連線狀況） |
| 6_todo_viewer 前端 | `cd 6_todo_viewer/frontend && npx vue-tsc --noEmit` | 無錯誤 |
| 7_proc_export 後端 | `cd 7_proc_export/backend && python -m pytest tests -q` | 17 項通過（不需資料庫） |
| 7_proc_export 前端 | `cd 7_proc_export/frontend && npx vue-tsc --noEmit` | 無錯誤 |

那 2 個跳過的是**真的會寫資料庫**的整合測試，需三個環境變數同時設齊才會執行；
跳過時會說明原因，不會假裝通過。

改動 `1_xml_tool/core/` 一定要跑 `node test_core.mjs` ——
它會用真實範例檔驗證「載入 → 修改 → 匯出」位元組層級可還原。
