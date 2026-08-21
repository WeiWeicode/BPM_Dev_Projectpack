# 專案計劃書：BPM 線上結構檢視器 (4_db_viewer)

> 狀態：**規劃中**，尚未實作。
> 架構：Python 後端 API + Vue 3 / Vite 前端。
> 前置相依：`3_db_explorer`（資料庫關聯邏輯）、`1_xml_tool/core`（XML 解析）。

---

## 1. 執行摘要

### 1.1 專案背景與痛點

`3_db_explorer` 已經能把線上的表單與流程撈出來，但產出是
`docs/BPM_知識重點.md` 與 `out/*.json` —— 適合 AI 讀、適合 code review，
**不適合人在瀏覽器裡快速查找**。實務上常見的問題是：

- 「這張表單有哪些欄位？ID 和中文名怎麼對應？」→ 現在要翻 JSON 或開設計師
- 「這個關卡上有哪些按鈕？誰能按？」→ 按鈕權限藏在二次逃脫的 XML 字串裡
- 「同一張表單在各關卡的差異在哪？」→ Markdown 表格在幾十個欄位時難以掃視
- 線上有 2848 個表單版本、7179 個流程套件版本，沒有搜尋與篩選根本找不到東西

### 1.2 產品目標

一個**前後端分離的網頁應用**，直接呈現資料庫裡的：

| 面向 | 要看到的欄位 |
| --- | --- |
| **表單** | 元件 `id`、`name`（中文顯示名）、`type`（元件型別） |
| **流程** | 關卡 `id`、關卡 `name`、該關卡的**按鈕權限** |

並且讓兩者可以互相對照 —— 點一個關卡，看到它掛的表單與該關卡的權限；
點一個表單欄位，看到它在各關卡分別是什麼權限。

### 1.3 三項既定決策

| # | 決策 | 說明 |
| --- | --- | --- |
| 1 | **只讀 RELEASED** | 只呈現已發佈版本，`UNDER_REVISION` 一律不撈 |
| 2 | **與專案 2 完全隔離** | 獨立應用，不共用程式碼、不共用進入點；本專案唯讀 |
| 3 | **前後端分離** | 後端 Python 提供 REST API，前端 Vue 3 + Vite |

### 1.4 與既有專案的分工

| 專案 | 資料來源 | 型態 | 讀者 |
| --- | --- | --- | --- |
| 2_web_builder | 本機 `.form` / `.bpmn` 檔 | 單檔靜態網頁 | 開發者，**寫**用途 |
| 3_db_explorer | 資料庫 | CLI + Markdown / JSON | AI、版控 |
| **4_db_viewer** | 資料庫（經由 3 的模組） | **前後端 Web 應用** | 開發者、PM，**讀**用途 |

本專案**唯讀**，不提供任何回寫功能 —— 要改東西請走 `2_web_builder`。
這條界線要守住，否則權限模型與版本控制會失控。

---

## 2. 系統架構

```
┌─────────────────────────────────────────────────────────────┐
│  瀏覽器                                                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Vue 3 + Vite  (frontend/)                            │  │
│  │  表單檢視 · 流程檢視 · 權限矩陣 · 全域搜尋               │  │
│  └───────────────────────────┬───────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────┘
                               │ HTTP / JSON
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  FastAPI  (backend/)                                        │
│  ┌──────────────┬──────────────┬───────────────────────┐    │
│  │  routers/    │  models.py   │  cache.py             │    │
│  │  REST 端點   │  Pydantic    │  記憶體 TTL 快取        │    │
│  └──────┬───────┴──────────────┴───────────────────────┘    │
│         │ import（不重寫 SQL）                                │
│         ↓                                                    │
│  3_db_explorer/bpm_kb/                                      │
│    extract.py · process_graph.py · db.py · config.py        │
└──────────────────────────────┬──────────────────────────────┘
                               │ pyodbc，唯讀連線
                               ↓
                    SQL Server (BPM 資料庫)
```

### 2.1 技術選型與理由

| 層 | 選擇 | 理由 |
| --- | --- | --- |
| 後端框架 | **FastAPI + uvicorn** | Pydantic 讓資料契約有型別保證，自動產生 `/docs` 互動文件，省掉手寫 API 說明 |
| 前端框架 | **Vue 3 `<script setup>` + TypeScript** | 使用者指定；TS 與後端 Pydantic 模型對得起來 |
| 建置工具 | **Vite** | 使用者指定；dev server 的 proxy 直接解決 CORS |
| 狀態管理 | **composables（不用 Pinia）** | 只有三個檢視、資料是唯讀快取，Pinia 是過度設計 |
| UI 元件庫 | **不用，手刻 CSS** | 內網不保證能連 CDN；沿用專案 2 的色票讓兩個網頁像同一家人 |
| 表格 | 原生 `<table>` | 單張表單約 27 個元件，不需要虛擬捲動；未來真的爆量再引入 TanStack Table（headless，不綁樣式） |

已驗證可用：Python 3.14.3 + FastAPI 0.141.1 + Pydantic 2.13.4、Node v24.14.0 + npm 11.12.0。

### 2.2 開發與部署模式

**開發**（兩個 process）：

```
uvicorn app.main:app --reload --port 8000     # 後端
npm run dev                                    # 前端 :5173，proxy /api → :8000
```

**部署**（單一 process）：`npm run build` 產出 `frontend/dist/`，
後端以 `StaticFiles` 掛在 `/`，只要跑 uvicorn 一個服務即可。

### 2.3 安全邊界

- 連線沿用 `bpm_kb.db.Database`，`readonly=True`，且只走既有的具名查詢
- **API 不接受任何 SQL 片段**，只接受 `keyword` / `limit` 等參數，全部走參數化查詢
- 預設只綁 `127.0.0.1`；要給同事用需明確指定 `--host`，並在 README 標註風險
- API 回應中的連線描述不含密碼（`config.describe()` 本來就不吐密碼）
- 沒有任何寫入端點（POST / PUT / DELETE 一律不提供）

---

## 3. 資料來源與關聯邏輯

完全沿用 `3_db_explorer` 已驗證的關聯路徑，**不重寫任何 SQL**：

```
表單元件（id / name / type）
  FormDefinition.defSerialize
    → core.form_handler.extract()
    → { formId, formName, fields: [{ id, name, type }] }

流程關卡（id / name）
  ProcessPackage → ProcessPackage_ProcessDef → ProcessDefinition
    → ActivityDefinition (containerOID = ProcessDefinition.OID)
    → { id, name, bpmnType, performType, performers }

關卡的按鈕與欄位權限
  ActivityDefinition.formFieldAccessDefinitionOID
    → FormFieldAccessDefinition.formFieldAccessControl
    → <FormFieldAccessControl><表單ID><元件ID>權限</元件ID>…</表單ID>
    → { formId, permissions: [{ id, permission }] }
```

對應模組：`bpm_kb/extract.py`、`bpm_kb/process_graph.py`。

### 3.1 只讀 RELEASED（決策 1）

現有的 `list_forms()` / `list_processes()` 已支援 `keyword` / `since_days` /
`latest_only`，**需新增 `released_only` 參數**：

```sql
-- 表單：欄位就在 FormDefinition 上
WHERE f.publicationStatus = 'RELEASED'

-- 流程：狀態在 RedefinableHeader
WHERE r.publicationStatus = 'RELEASED'
```

後端一律以 `released_only=True` 呼叫，不開放前端關閉。
這個參數加在 `bpm_kb` 內，`3_db_explorer` 的 CLI 也能一併受益。

> 實測影響：測試流程 `quickDevTestProcessImport` 的 v1、v2 是
> `UNDER_REVISION` 會被濾掉，只留 v3；`quickDevTestProcessImportWebTool`
> 只留 v2。這正是我們要的 —— 線上真正生效的版本。

### 3.2 關鍵改進：按鈕要用表單型別判定，不要猜 ID

目前 `process_graph._is_button()` 是用 ID 命名（含 `button` / `btn`）猜的，
`SubmitBtn` 猜得到，`TEST_Confirm_09` 就猜不到。

後端同時持有表單元件清單與關卡權限清單，**可以直接 join**：

```
form.fields  [{ id: 'TEST_Button_06', type: 'BUTTON' }]
                        │ 用 id 對接
activity.permissions [{ id: 'TEST_Button_06', permission: 'ENABLED' }]
                        ↓
              確定這是按鈕，不是猜的
```

`core/form_handler.py` 的 `CLASS_TYPE_MAP` 已把 `TriggerElementDefinition`
對應成 `BUTTON`，型別是可信的。實作時應把這個 join 邏輯回饋給
`process_graph.py`，讓 `3_db_explorer` 的產出也一併變準。

### 3.3 權限值（資料庫實測，取樣 4000 筆）

| 值 | 佔比 | 意義 |
| --- | --- | --- |
| `ENABLED` | ~98% | 可編輯／可按 |
| `INVISIBLE` | ~1.3% | 隱藏 |
| `FULL_CONTROL` | ~0.3% | 完全控制 |
| （未列出） | — | 該關卡未設定，沿用表單預設 |

UI 的色彩與圖例以這四種狀態為準，不要自行發明 `READ_ONLY` 之類的值。

### 3.4 表單版本解析規則（決策 1 的延伸）

關卡的 `formFieldAccessControl` 只記表單 **ID**，不記版本。對照規則：

1. 取該表單 `publicationStatus = 'RELEASED'` 且 `version` 最大的一版
2. 對照不到（欄位在權限清單、但不在表單定義中）→ API 回傳
   `"orphaned": true`，UI 明確標示「此元件在目前表單版本中不存在」

第 2 種情況代表流程版本與表單版本脫節，本身就是值得看見的問題，
**不可以靜默忽略**。

### 3.5 效能與快取

`pull` 全量跑一次要撈幾千份 XML，不可能每次 API 呼叫都做。策略：

- `cache.py` 提供記憶體 TTL 快取（預設 10 分鐘），key 為
  `(endpoint, 參數)`；表單元件明細以 `formId` 為 key 單獨快取
- 清單端點只查中繼欄位（不撈 `defSerialize`），本來就快
- 明細端點才撈 XML 並解析，屬於 lazy load
- 提供 `POST /api/cache/clear`？→ **不提供**，唯讀原則優先；
  改用啟動參數 `--cache-ttl` 調整，需要立即更新就重啟服務

---

## 4. API 設計

前綴一律 `/api`。全部為 `GET`。

| 端點 | 說明 | 主要參數 |
| --- | --- | --- |
| `/api/health` | 連線狀態、資料庫名稱、快取統計 | — |
| `/api/forms` | 表單清單（RELEASED、每個 id 最新版） | `keyword`, `days`, `limit`, `offset` |
| `/api/forms/{form_id}` | 單一表單的元件明細 **id / name / type** | — |
| `/api/forms/{form_id}/usage` | 這張表單被哪些流程的哪些關卡使用 | — |
| `/api/processes` | 流程清單（RELEASED、每個 id 最新版） | `keyword`, `days`, `limit`, `offset` |
| `/api/processes/{process_id}` | 關卡明細 **id / name / 按鈕權限** + 連線 | — |
| `/api/processes/{process_id}/matrix` | 關卡 × 元件的權限矩陣 | `only`（`button` / `field` / `all`） |
| `/api/search` | 全域搜尋：表單 ID、元件 ID、中文名、關卡 ID、關卡名 | `q`（必填，至少 2 字） |

### 4.1 Pydantic 模型（資料契約）

```python
class FormField(BaseModel):
    id: str
    name: str                    # 配對 Label 的中文名
    type: str                    # TEXTBOX / BUTTON / GRID / ...

class FormDetail(BaseModel):
    form_id: str
    form_name: str
    version: int
    created_time: datetime
    fields: list[FormField]

class ActivityPermission(BaseModel):
    id: str
    name: str = ''               # 由表單定義 join 進來
    type: str = ''               # 同上；空字串代表對照不到
    permission: Literal['ENABLED', 'INVISIBLE', 'FULL_CONTROL']
    orphaned: bool = False       # 見 3.4

class Activity(BaseModel):
    id: str
    name: str
    bpmn_type: str               # StartEvent / UserTask / SendTask / ...
    perform_type: str            # NORMAL / NOTICE
    performers: list[str]        # PROCESS_REQUESTER / MANAGER / SYSTEM
    form_id: str = ''
    buttons: list[ActivityPermission]     # type == 'BUTTON'
    fields: list[ActivityPermission]      # 其餘

class Transition(BaseModel):
    from_id: str = Field(alias='from')
    to_id: str = Field(alias='to')
    has_condition: bool

class ProcessDetail(BaseModel):
    process_id: str
    process_name: str
    version: int
    flow_type: str               # SignatureFlow / ...
    activities: list[Activity]   # 已依 transitions 拓撲排序
    transitions: list[Transition]
```

Pydantic 模型以 `openapi.json` 匯出，前端用 `openapi-typescript` 產生
TypeScript 型別 —— **契約只有一份，不手抄**。

### 4.2 回應範例

`GET /api/processes/quickDevTestProcessImportWebTool`

```jsonc
{
  "process_id": "quickDevTestProcessImportWebTool",
  "process_name": "測試快速開發(webTool)",
  "version": 2,
  "flow_type": "SignatureFlow",
  "activities": [
    { "id": "ACT_Start_03", "name": "Event", "bpmn_type": "StartEvent",
      "perform_type": "NORMAL", "performers": [], "form_id": "",
      "buttons": [], "fields": [] },
    { "id": "ACT_CreateForm_06", "name": "開單", "bpmn_type": "UserTask",
      "perform_type": "NORMAL", "performers": ["PROCESS_REQUESTER"],
      "form_id": "quickDevTestFormImport",
      "buttons": [
        { "id": "TEST_Button_06", "name": "按鈕", "type": "BUTTON",
          "permission": "ENABLED", "orphaned": false }
      ],
      "fields": [
        { "id": "TEST_TextBox_07", "name": "輸入框", "type": "TEXTBOX",
          "permission": "ENABLED", "orphaned": false }
      ] }
  ],
  "transitions": [
    { "from": "ACT_Start_03", "to": "ACT_CreateForm_06", "has_condition": false }
  ]
}
```

---

## 5. 前端規劃

### 5.1 版面

```
┌─────────────────────────────────────────────────────────┐
│  BPM 線上結構檢視器          NaNa · RELEASED · 快取 3 分鐘前 │
│  [🔍 搜尋 ID / 名稱 ..............]   [表單] [流程] [矩陣]  │
├───────────────┬─────────────────────────────────────────┤
│ 左側清單       │  右側明細                                 │
│               │                                          │
│ ▸ 表單 (12)   │  依左側選取的項目切換內容                    │
│   快速開發測試  │                                          │
│   請假單       │                                          │
│ ▸ 流程 (8)    │                                          │
│   測試快速開發  │                                          │
└───────────────┴─────────────────────────────────────────┘
```

### 5.2 三個檢視（對應 Vue Router 三條路由）

**① `/forms/:id` 表單檢視** —— 你要的 id / name / type

| 元件 ID | 名稱 | 型別 | 被哪些關卡使用 |
| --- | --- | --- | --- |
| TEST_TextBox_07 | 輸入框 | TEXTBOX | 開單、主管 |
| TEST_Button_06 | 按鈕 | BUTTON | 開單、主管 |

**② `/processes/:id` 流程檢視** —— 你要的關卡 id / name / 按鈕權限

| 關卡 ID | 關卡名稱 | 型別 | 執行者 | 表單 | 按鈕權限 |
| --- | --- | --- | --- | --- | --- |
| ACT_CreateForm_06 | 開單 | UserTask | PROCESS_REQUESTER | quickDevTestFormImport | 按鈕 `ENABLED` |
| ACT_ManagerApprove_02 | 主管 | UserTask | MANAGER | quickDevTestFormImport | 按鈕 `ENABLED` |

關卡順序由後端依 `transitions` 拓撲排序後回傳
（`process_graph.order_activities()` 已實作），
表格上方以文字流呈現：`開單 → 主管 → 通知任務 → 人工任務`。

**③ `/processes/:id/matrix` 矩陣檢視** —— 關卡 × 元件權限

|  | 開單 | 主管 | 人工任務 |
| --- | --- | --- | --- |
| TEST_TextBox_07（輸入框） | ENABLED | ENABLED | — |
| **TEST_Button_06（按鈕）** | ENABLED | INVISIBLE | — |

- 按鈕列以不同底色標示，與一般欄位區隔（你特別點名要看的）
- 可切換「只看按鈕 / 只看欄位 / 全部」（打 `?only=button`）
- 橫向捲動，第一欄 `position: sticky` 凍結

### 5.3 元件切分

```
src/
├── api/client.ts            fetch 封裝 + 錯誤處理
├── api/types.ts             由 openapi-typescript 產生，勿手改
├── composables/
│   ├── useForms.ts          清單與明細的載入與快取
│   ├── useProcesses.ts
│   └── useSearch.ts         debounce 300ms
├── components/
│   ├── AppHeader.vue        搜尋框、檢視切換、連線狀態
│   ├── EntityList.vue       左側清單（表單／流程共用）
│   ├── FieldTable.vue       元件表格（id / name / type）
│   ├── ActivityTable.vue    關卡表格（含按鈕權限欄）
│   ├── PermissionBadge.vue  權限色塊，四種狀態
│   ├── PermissionMatrix.vue 矩陣，含凍結欄與篩選
│   └── FlowPath.vue         `開單 → 主管 → …` 文字流
└── views/
    ├── FormsView.vue
    ├── ProcessesView.vue
    └── MatrixView.vue
```

### 5.4 互動細節

- 權限色塊：`ENABLED` 綠、`INVISIBLE` 灰、`FULL_CONTROL` 藍、未設定 `—` 淡色
- `orphaned` 元件加紅色邊框與 tooltip「此元件在目前表單版本中不存在」
- 點任一元件 ID → 高亮它在所有關卡的權限
- 點擊 ID 即複製到剪貼簿（開發時常要貼到程式碼裡），並顯示 toast
- 匯出目前檢視為 CSV，方便貼進 Excel 給 PM
- 載入中骨架屏、空狀態、API 失敗的明確錯誤訊息（含後端是否啟動的提示）

---

## 6. 預定檔案結構

```
4_db_viewer/
├── PLAN.md                   本檔
├── README.md                 （P5）安裝與使用說明
├── backend/
│   ├── requirements.txt      fastapi, uvicorn[standard]
│   ├── app/
│   │   ├── main.py           FastAPI 實例、CORS、靜態檔掛載
│   │   ├── settings.py       埠號、快取 TTL、bpm_kb 路徑解析
│   │   ├── cache.py          記憶體 TTL 快取
│   │   ├── models.py         Pydantic 模型（第 4.1 節）
│   │   ├── service.py        呼叫 bpm_kb、組資料、做型別 join
│   │   └── routers/
│   │       ├── forms.py
│   │       ├── processes.py
│   │       └── meta.py       health / search
│   └── tests/
│       └── test_service.py   用 out/*.json 當 fixture，不需連線
└── frontend/
    ├── package.json
    ├── vite.config.ts        proxy /api → localhost:8000
    ├── tsconfig.json
    ├── index.html
    └── src/                  （第 5.3 節）
```

`bpm_kb` 的匯入方式沿用專案 3 既有的做法 —— `settings.py` 解析出
`3_db_explorer` 路徑後加進 `sys.path`，不複製程式碼、不做成套件安裝。

---

## 7. 實作階段

| 階段 | 內容 | 驗收 |
| --- | --- | --- |
| **P0** | `bpm_kb` 加 `released_only` 參數（3.1）；型別 join 邏輯（3.2） | 既有 CLI 加 `--released` 可跑；`3_db_explorer` 產出的按鈕判定變準 |
| **P1** | 後端骨架：`main.py` / `settings.py` / `models.py` / `health` | `/api/health` 回連線狀態，`/docs` 可開 |
| **P2** | `service.py` + forms / processes 端點 + 快取 | API 回得出第 4.2 節的結構；`test_service.py` 通過 |
| **P3** | 前端骨架：Vite + Vue + Router + `client.ts` + 型別產生 | `npm run dev` 能打到後端並列出清單 |
| **P4** | 表單檢視 + 流程檢視 | 你要的 id / name / type、關卡 id / name / 按鈕權限全部可看 |
| **P5** | 矩陣檢視、搜尋、CSV 匯出、README、建置流程 | 可交付 |

P0、P1、P2 完全不依賴前端，可以先做完並用 `/docs` 驗證。

---

## 8. 驗收標準

1. `uvicorn` 起得來，`/api/health` 回報資料庫名稱與連線狀態
2. `/docs` 可開，所有端點有完整的 Pydantic 結構描述
3. 表單明細完整列出元件的 id / name / type，數量與 `out/forms/*.json` 一致
4. 流程明細完整列出關卡的 id / name，順序與 `transitions` 拓撲一致
5. **只回傳 RELEASED 版本**，`UNDER_REVISION` 不出現在任何回應中
6. 按鈕權限來自表單型別 join（`type == 'BUTTON'`），不是 ID 命名猜測
7. 權限值只出現 `ENABLED` / `INVISIBLE` / `FULL_CONTROL` / 未設定四種
8. 權限清單中有、但表單定義中不存在的元件，標為 `orphaned` 並在 UI 呈現
9. API 回應不含資料庫密碼；沒有任何寫入端點
10. `npm run build` 後單跑 uvicorn 即可完整使用（不需 Vite dev server）
11. 後端預設只綁 `127.0.0.1`

---

## 9. 風險與對策

| 風險 | 對策 |
| --- | --- |
| 首次載入大表單時解析 XML 慢（單檔約 220 KB） | 明細端點 lazy load + TTL 快取；清單端點不碰 XML |
| 內網無法 `npm install` | 先在可連外的機器 `npm ci` 後整包搬入，或設定公司 registry |
| `bpm_kb` 介面變動導致後端壞掉 | `test_service.py` 用 `out/*.json` 當 fixture，介面一變就紅燈 |
| 使用者誤以為可以在此修改 | UI 明確標示「唯讀檢視」，並在 README 指向 `2_web_builder` |
| 多人同時使用打爆資料庫 | 快取 + 唯讀連線；真的要多人用再評估連線池 |

---

## 10. 後續擴充

- 流程圖視覺化（`bpmXML` 已有畫布座標，可直接畫出關卡位置與連線）
- 版本 diff：比較同一表單／流程的兩個版本，標出欄位與權限差異
- 反向查詢的完整版：某個欄位 ID 被哪些流程的哪些關卡用到（跨流程影響分析）
- 條件式展開：`TransitionDefinition.conditionOID` 目前只知有無，未解析內容
