# 4_db_viewer —— BPM 線上結構檢視器

前後端分離的網頁應用，唯讀呈現 BPM 資料庫中**已發佈（RELEASED）**的表單與流程結構。
設計背景與決策見 [PLAN.md](PLAN.md)；整體專案脈絡見 [repo 根目錄 README](../README.md)。

**預設唯讀。** 另有一條受嚴格限制的寫入路徑，只能改權限值、預設關閉，見下方
「權限快速開發」。要做結構性變更（加減元件、改關卡）仍請走 `2_web_builder`。

---

## 快速開始

### 1. 後端

**一般模式（預設唯讀）：**

```bash
cd 4_db_viewer/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

**編輯模式（啟用權限寫入，需指定流程白名單）：**

- **PowerShell (Windows)**:
  ```powershell
  $env:BPM_VIEWER_ENABLE_WRITE="1"; $env:BPM_VIEWER_WRITABLE_PROCESSES="流程ID"; python -m uvicorn app.main:app --reload --port 8000
  ```
    ```powershell
  $env:BPM_VIEWER_ENABLE_WRITE="1"; $env:BPM_VIEWER_WRITABLE_PROCESSES="quickDevTestProcessImportWebTool"; python -m uvicorn app.main:app --reload --port 8000
  ```
- **Bash / Linux / macOS**:
  ```bash
  BPM_VIEWER_ENABLE_WRITE=1 BPM_VIEWER_WRITABLE_PROCESSES=流程ID python -m uvicorn app.main:app --reload --port 8000
  ```
- **CMD (Windows)**:
  ```cmd
  set BPM_VIEWER_ENABLE_WRITE=1&& set BPM_VIEWER_WRITABLE_PROCESSES=流程ID&& python -m uvicorn app.main:app --reload --port 8000
  ```

連線設定沿用 `3_db_explorer` 的 `.env`（本專案不另外存帳密）。
啟動後 <http://127.0.0.1:8000/docs> 可看互動式 API 文件。

### 2. 前端（開發模式）

```bash
cd 4_db_viewer/frontend
npm install
npm run dev
```

開 <http://localhost:5173>，Vite 會把 `/api` 轉給後端的 8000 埠。

### 切換資料庫主機

標題列的下拉可切換主機，預設兩台：

| key | 標籤 | 位址 | 可寫 |
| --- | --- | --- | --- |
| `191` | BPM 191 測試區 | 10.10.130.191 | ✔ |
| `190` | BPM 190 正式區 | 10.10.130.190 | ✘ |

切到正式區時下拉會變紅框、旁邊出現紅色「正式區」標記，徽章自動變回「唯讀」，
編輯功能整組消失。選擇會存進 localStorage，重新整理後保持。

主機清單可用 `BPM_VIEWER_HOSTS` 覆寫，格式 `key|標籤|位址|是否正式區`，逗號分隔：

```bash
BPM_VIEWER_HOSTS="191|測試區|10.10.130.191|0,190|正式區|10.10.130.190|1"
```

兩台帳密不同時，用 `BPM_DB_USER_<key>` / `BPM_DB_PASSWORD_<key>` / `BPM_DB_NAME_<key>`
個別覆寫，例如 `BPM_DB_PASSWORD_190`。沒設就沿用 `.env` 的共用設定。

主機是**每個請求的參數**，後端不存「目前主機」狀態，兩台的快取也各自獨立
（快取 key 帶主機前綴），多人同時看不同主機不會互相干擾。

### 3. 正式使用（單一 process）

```bash
cd 4_db_viewer/frontend
npm run build
```

建置產物在 `frontend/dist/`，後端偵測到就會直接掛載。
之後只要跑 uvicorn 一個服務，開 <http://127.0.0.1:8000> 即可。

---

## 三個檢視

| 路徑 | 內容 |
| --- | --- |
| `/forms/:id` | 表單元件的 **id / name / type**，以及這張表單被哪些關卡使用 |
| `/processes/:id` | 關卡的 **id / name / BPMN 型別 / 執行者 / 表單 / 按鈕權限** |
| `/matrix/:id` | 關卡 × 元件的權限矩陣，可切換「只看按鈕 / 只看欄位」 |

三個檢視都支援全域搜尋（比對 ID 與中文名）、點 ID 複製、匯出 CSV。

### 矩陣頁的篩選與排序

- **篩選元件**：工具列左側的輸入框，比對元件 ID 與中文名，即時過濾列，
  旁邊顯示「N / M 個元件」
- **排序**：表頭可點 —— 元件 ID／名稱／型別，或任一關卡欄（依權限排序，
  可編輯 → 完全控制 → 隱藏 → 唯讀 → 不適用）。
  同一個鍵連點三次循環：升冪 → 降冪 → 回到表單定義的原始順序
- **匯出 CSV 匯的是目前看到的內容**，含篩選與排序結果

### 權限值

| 值 | 意義 |
| --- | --- |
| `ENABLED` | 可編輯／可按（設計師 UI：可編輯(Enable)） |
| `INVISIBLE` | 隱藏（設計師 UI：隱藏(Invisible)） |
| `FULL_CONTROL` | 完全控制 |
| `—` | **未列出 = 唯讀(Disable)**，不是「沿用預設」 |
| 紅框 | `orphaned`：權限清單有、但表單定義中已無此元件 |

資料庫只存前三種值（20,000 筆取樣）。要把元件設成唯讀，作法是
**把它從權限字串中移除** —— 這是對照 BPM 設計師 UI 才確認的，
`lbl_TEST_Hidden_01` 不在字串中，設計師顯示「唯讀(Disable)」。

**紅框是要注意的訊號**，代表流程版本與表單版本脫節。

---

## 權限快速開發（寫入）

預設**完全關閉** —— 沒開旗標時寫入路由根本不會註冊。要啟用需同時給兩個環境變數：

- **PowerShell (Windows)**:
  ```powershell
  $env:BPM_VIEWER_ENABLE_WRITE="1"; $env:BPM_VIEWER_WRITABLE_PROCESSES="流程ID1,流程ID2"; python -m uvicorn app.main:app --port 8000
  ```
- **Bash / Linux / macOS**:
  ```bash
  BPM_VIEWER_ENABLE_WRITE=1 BPM_VIEWER_WRITABLE_PROCESSES=流程ID1,流程ID2 python -m uvicorn app.main:app --port 8000
  ```

白名單留空代表全部禁止 —— 就算開了旗標也不會誤傷。

啟用後，矩陣頁會出現「編輯權限」按鈕：每格變成下拉選單，改動先進 pending
區（黃底），按「預覽差異」看 舊值 → 新值，確認後才「套用」。
套用完會顯示備份 ID，旁邊有「還原這次變更」。

**「整欄設為…」只作用在目前篩選出的元件上。** 有篩選時下拉會顯示
「設定篩選出的 N 個…」，沒篩選時才是整欄。套用後的提示會分開回報
「標記 N 項變更」與「M 個已是此狀態」—— 本來就是該狀態的不算變更。

### 十道防護

| # | 防護 |
| --- | --- |
| 1 | **共用列偵測**：權限列被 >1 個關卡引用就拒絕（線上最多一列被 24,765 個關卡共用） |
| 2 | **預設關閉**：沒有 `BPM_VIEWER_ENABLE_WRITE=1` 連路由都不存在 |
| 3 | **流程白名單**：`BPM_VIEWER_WRITABLE_PROCESSES`，空值 = 全禁 |
| 3b | **主機白名單**：`BPM_VIEWER_WRITABLE_HOSTS`，**預設只含非正式區** —— 切到 190 一律拒絕 |
| 4 | **強制備份**：寫入前存到 `backend/backups/`，備份失敗就不寫 |
| 5 | **稽核紀錄**：`backups/audit.log` 記錄時間、來源 IP、每個元件的 舊值 → 新值 |
| 6 | **兩段式**：先 preview 拿 token，apply 必須帶 token |
| 7 | **值白名單**：只接受四種值，`INVALIDITY` 因格式未知不支援 |
| 8 | **rowcount 驗證**：`UPDATE` 影響列數不是 1 就 rollback |
| 9 | **寫後回讀**：不一致就自動用備份還原並回報失敗 |
| 10 | **一鍵還原**：`POST /api/write/restore/{backup_id}` |

token 是目前內容的雜湊 —— 期間若有人改過同一筆，套用會被擋下並要求重新預覽。

### 只做最小字串編輯

改值就替換那一段，設唯讀就移除該標籤，給新權限就插在表單區塊結尾前。
未觸及的部分**位元組不變**，與 `1_xml_tool` 的無損原則一致。

### 使用前必讀的風險

- 這條路徑**繞過 BPM 的版本控制**，設計師 UI 看不出改過
- `objectVersion` 預設不遞增（`BPM_VIEWER_BUMP_OBJECT_VERSION=1` 可開，但**未驗證**）。
  意思是日後若有人從設計師開啟這支流程再存檔，你的改動會被**靜默覆蓋**
- 尚未驗證執行中的流程實例會不會吃到新權限
- 正式區**預設就寫不進去**（`BPM_VIEWER_WRITABLE_HOSTS` 不含它）。
  真要開放必須明確設定，開之前請先確認共用列檢查有生效

---

## API

前綴 `/api`。唯讀端點全為 `GET`；寫入端點只在旗標開啟時存在。完整結構見 `/docs`。

| 端點 | 說明 |
| --- | --- |
| `/api/health` | 連線狀態、資料庫名稱、快取統計 |
| `/api/forms` | 表單清單（`keyword` / `limit` / `offset`） |
| `/api/forms/{form_id}` | 元件明細 |
| `/api/forms/{form_id}/usage` | 被哪些流程的哪些關卡使用 |
| `/api/processes` | 流程清單 |
| `/api/processes/{process_id}` | 關卡明細與連線 |
| `/api/processes/{process_id}/matrix` | 權限矩陣（`only=all\|button\|field`） |
| `/api/search` | 搜尋表單、流程、關卡（`include_fields=true` 才掃元件，很慢） |

寫入端點（需旗標）：

| 端點 | 說明 |
| --- | --- |
| `POST /api/processes/{pid}/activities/{aid}/permissions/preview` | 回傳差異與 token，不寫入 |
| `PATCH /api/processes/{pid}/activities/{aid}/permissions` | 套用，需帶 token |
| `GET /api/write/backups` | 列出備份 |
| `POST /api/write/restore/{backup_id}` | 由備份還原 |

### 型別契約

`backend/app/models.py` 的 Pydantic 模型是唯一真實來源。前端型別由它產生：

```bash
cd backend && python dump_openapi.py
cd ../frontend && npm run gen:types
```

`frontend/src/api/types.ts` 是產生物（已 gitignore），**不要手改**。
改動 API 結構後要重跑上面兩步。

---

## 架構重點

```
frontend/  Vue 3 <script setup> + TypeScript + Vite，手刻 CSS，無 UI 框架
    │ HTTP
backend/   FastAPI，只註冊 GET 端點
    │ import（不重寫 SQL）
3_db_explorer/bpm_kb/   extract.py · process_graph.py · db.py
    │ pyodbc readonly=True
SQL Server
```

### 為什麼按鈕判定要靠表單型別

`process_graph._is_button()` 原本用 ID 命名猜（只比對 `_` 邊界），
`SubmitBtn`、`TEST_Confirm_09` 都猜不到。本專案同時持有表單元件清單與關卡權限，
直接用 `type == 'BUTTON'` 對接，判定才可靠。這個邏輯已回饋給
`bpm_kb/process_graph.py`，`3_db_explorer` 的產出一併受益。

反例：`TEST_RadioButton_15` 名字裡有 `RadioButton`，但型別是 `RADIO`，
不是按鈕 —— 靠命名猜會判錯，靠型別就不會。

### 效能：不要整批撈 ntext

`FormFieldAccessDefinition.formFieldAccessControl` 全部撈出來是
**860 MB / 55 秒**。但表單 ID 就寫在字串開頭，只取前 200 字元建索引是
**0.44 MB / 0.4 秒**（見 `service._usage_index`）。

其餘查詢有 10 分鐘記憶體快取（`BPM_VIEWER_CACHE_TTL` 可調）。
結構不會分秒變動；需要立即反映異動就重啟服務。

---

## 測試

```bash
cd 4_db_viewer/backend
python -m pytest tests -q
```

33 項：按鈕型別判定、`orphaned` 標記、分頁與篩選、矩陣組裝、快取，
以及寫入引擎的字串編輯、往返還原、防護拒絕（含正式區禁寫）。
純邏輯測試不需要資料庫；需要連線的測試在連不上時**跳過並說明原因**，不會假裝通過。

**真的會寫資料庫**的整合測試預設跳過，要跑必須三個環境變數同時設齊：

```bash
BPM_VIEWER_ENABLE_WRITE=1 BPM_VIEWER_WRITABLE_PROCESSES=quickDevTestProcessImportWebTool BPM_VIEWER_WRITE_TEST=1 python -m pytest tests -q
```

前端型別檢查：

```bash
cd 4_db_viewer/frontend && npx vue-tsc --noEmit
```

---

## 安全

- 唯讀查詢走 `bpm_kb.db.Database`（`readonly=True`）；寫入另開連線於 `app/writer.py`，
  兩者不共用，讓「唯讀」在型別層面就看得出來。`3_db_explorer` 完全不受影響
- 不開旗標時沒有任何寫入端點
- API 不接受 SQL 片段，只接受 `keyword` / `limit` 等參數，全部參數化查詢
- 回應中的連線描述不含密碼
- 預設只綁 `127.0.0.1`。要給同事使用需明確指定 `--host 0.0.0.0`，
  但請注意這等於把資料庫內容對整個網段開放，**沒有任何身分驗證**

---

## 已知限制

- `/api/search` 預設不搜尋表單元件，因為那需要解析所有已發佈表單的 XML。
  加 `include_fields=true` 可啟用，首次會很慢（之後有快取）。
- 只呈現最新的 RELEASED 版本，看不到歷史版本或修訂中的版本。
- `TransitionDefinition.conditionOID` 目前只知有無條件，未展開條件內容。
- 沒有流程圖視覺化 —— `bpmXML` 有畫布座標可用，列為後續擴充。
