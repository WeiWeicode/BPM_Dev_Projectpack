# 7_proc_export —— 流程與表單匯出

為稽核調閱而做：挑一支流程 → 查單 → 看表單內容 → 把**清單／表單內容／簽核名單**
匯成單一 Excel 的不同 tab。

**唯讀。** 只有查詢與匯出，沒有任何寫入端點。

## 能匯出什麼

| 工作表 | 內容 |
|:---|:---|
| 匯出條件 | 資料來源、流程、日期區間、篩選條件、筆數、欄位名稱覆蓋率 |
| 清單 | 流程單號、表單單號、主旨、申請人、部門、申請日期、狀態、結案時間、歷時、目前關卡與待辦人、作廢／終止原因 |
| 內容 | 上述單頭 + 你勾選的表單欄位，一欄一個欄位 |
| 明細-*表格名* | 表格控件的明細，一列一筆，帶流程單號可回連主表。每個表格自成一個工作表 |
| 欄位對照 | 每一欄的欄位 ID、型別、名稱是哪裡來的 —— 稽核要能回推 |
| 簽核名單 | 每張單每個關卡一列：關卡名稱、簽核人、收件／完成時間、停留天數、狀態、簽核意見 |

三個匯出項目（清單／內容／簽核名單）可任選，全部寫進同一個檔案。

## 跑起來

```bash
cd 7_proc_export/backend && pip install -r requirements.txt
```

```bash
cd 7_proc_export/backend && python -m uvicorn app.main:app --reload --port 8002
```

```bash
cd 7_proc_export/frontend && npm install && npm run dev
```

開發時開 <http://localhost:5176>（Vite 會把 `/api` 轉給 8002）。
`npm run build` 之後後端會直接吐 `frontend/dist`，只跑 uvicorn 開
<http://127.0.0.1:8002> 就有完整畫面。

## 連線設定

資料庫連線沿用 `3_db_explorer/.env`（本專案不另外放 `.env`，
`bpm_kb.config` 只會去找 `3_db_explorer/.env` 或 repo 根目錄的 `.env`）。

畫面右上可切換 191 測試區 / 190 正式區，**兩區都是唯讀**。
兩區帳密相同時什麼都不必設；不同時用環境變數覆寫：

| 環境變數 | 用途 |
|:---|:---|
| `BPM_DB_USER_190` / `BPM_DB_PASSWORD_190` / `BPM_DB_NAME_190` | 正式區專屬帳密 |
| `BPM_EXPORT_HOSTS` | 覆寫主機清單，格式 `key\|標籤\|位址\|是否正式區`，逗號分隔 |
| `BPM_EXPORT_MAX_ROWS` | 單次匯出上限，預設 20000 |
| `BPM_EXPORT_MAX_SCAN` | 自訂欄位條件的掃描上限，預設 50000 |
| `BPM_EXPORT_FIELD_SAMPLE` | 建欄位清單時抽樣的單據數，預設 200 |

> **190 是正式區。** 這裡開放的只有唯讀 SQL 查詢。SOAP API 對 190
> 仍然一律禁止（見 `AGENTS.md` 8.1），本專案也完全不呼叫 SOAP。

## 資料是怎麼串起來的（實測驗證，不要重推一次）

```
ProcessInstance.contextOID
  → LocalRelevantData.containerOID      id = 表單 id、valueOID = 表單實例
  → FormInstance.OID                    fieldValues = 表單 XML、serialNumber = 表單單號

ProcessInstance.contextOID
  → WorkItem.contextOID                 簽核歷程：關卡、簽核人、時間、意見
```

這條路徑是**實例層**的關聯，跟 `AGENTS.md` 7.1 講的「定義層有兩個來源、38 支查不到」
是兩回事 —— 實例層每一張單都問得到自己掛哪張表單，不需要猜。

**流程單號 ≠ 表單單號。** `ProcessInstance.serialNumber` 是 `SHROT_00004620` 這種，
`FormInstance.serialNumber` 是 `E071320320` 這種，兩者不能互相 join，
畫面與匯出都分成兩欄。

**一個流程的 `LocalRelevantData` 有多列變數**（實測 `GeneralAffairs` 每張單 3 列），
但真正指向 `FormInstance` 的**恰好 1 列**（抽樣 3 萬個 context 皆然）。
直接 `LEFT JOIN` 會讓同一張單重複出現，並多出表單單號空白的假列 ——
這個 bug 真的發生過（20 張單查出 60 筆），改用

```sql
OUTER APPLY (
    SELECT TOP 1 l.id AS formId, f.serialNumber, ...
    FROM LocalRelevantData l
    JOIN FormInstance f ON f.OID = l.valueOID
    WHERE l.containerOID = p.contextOID
    ORDER BY l.id
) AS fi
```

修掉。用 `OUTER` 而非 `CROSS` 是為了讓沒掛表單的單照樣列得出來。
`tests/test_export.py` 有結構測試守著，不要退回 `LEFT JOIN`。

表單內容的結構：

```xml
<表單id>
  <欄位id id="欄位id" dataType="java.lang.String">值</欄位id>
  <Grid11 id="Grid11">
    <records>
      <record id="Grid11_0">
        <item id="G_s_Sys_Name">值</item>
```

有 `<records>` 的就是表格控件，不能塞進單頭的一格，故另開工作表。

`DIALOGINPUT` 類欄位的內文是工號、`label` 屬性才是姓名，兩者都有時輸出
「姓名 (工號)」—— 只取內文的話稽核文件上會是一串看不懂的代碼。

## 欄位名稱的實話

需求是「欄位以名稱呈現」，但**鼎新的表單定義裡，輸入欄位本身沒有存中文名稱**。
實測 3 張表單把所有可能來源都翻過：

| 來源 | 有中文的比例 |
|:---|:---|
| 元件 `name` | 0 / 147 |
| 元件 `hint` | 0 / 147 |
| 元件 `caption` | 9 / 147 |
| `multiZhMap`（多語系） | 2,624 筆全空 |

中文字都在版面上獨立的 Label 元件（`OutputElementDefinition`）。
本專案沿用 `4_db_viewer` 的做法（`bpm_kb.extract.parse_form` →
`core.form_handler` 的 `lbl_<id>` / `pairId` 配對）：

- **新表單**（設計時有填標籤）命中率高，例如 `quickDevTestFormImport` 是 100%。
- **舊表單**很低。依單據數排前 25 張表單實測，整體只有 **45%（414/923）**：
  `apmt720` 54%、`aimi150` 67%、`aapt330` 92%，但 `OT_Application`、
  `Errand_Application` 是 0%，`cpmt900` 只有 3%。

**配不到就顯示欄位 ID，畫面上用灰色斜體標示**，Excel 則另附「欄位對照」工作表。
**刻意不用座標鄰近去猜** —— 實測會配錯（`s_DeptID_txt` 會被配成「部門名稱」，
正確是「部門代號」），稽核文件上欄位名稱標錯比標 ID 更糟。

例外是**表格明細**：`ListElementDefinition/listItems/ListItem` 的 `<caption>`
是設計師實際填的欄位標題，實測 100% 有中文，明細工作表的欄位名稱可靠。

單張明細面板的欄位名稱走 `FormInstance.definitionOID`，**取這張單當時那一版定義**
（做法沿用 `6_todo_viewer`）—— 表單改過版時，用最新版的名稱會對不上。
匯出做不到這件事：一份 Excel 只有一列表頭，跨年份的單會用到不同版定義，
故匯出表頭固定取最新已發佈版，差異只影響改過名稱的欄位。

## 效能與上限

| 操作 | 實測 |
|:---|:---|
| 流程清單（GROUP BY 55 萬列） | 1.7 秒，有快取 |
| 單一流程 + 日期區間 | 0.05 秒 |
| 撈 200 張單含表單 XML | 0.11 秒 |
| 200 張單的簽核歷程 | 0.14 秒 |
| 89 張單匯出完整 Excel（6 個工作表） | 1.4 秒 / 77 KB |

**日期區間必填。** 不是為了保護資料庫（查詢很快），而是因為逐欄展開後一列可能
上百欄，兩萬列已接近開得起來的 Excel 上限。超過上限會直接擋下並要求縮小範圍，
不會偷偷只匯前面幾筆。

**自訂欄位條件是在 Python 端比對的。** `fieldValues` 是 ntext、55 萬列，
對它下 SQL `LIKE` 會全表掃描（實測 120 秒未回）。所以流程 + 日期會先把候選壓到
`BPM_EXPORT_MAX_SCAN` 以內再逐張解析；壓到上限時畫面會明說「只比對了部分單據」。

## 狀態代碼

`ProcessInstance.currentState`：

| 值 | 意義 | 依據 |
|:---|:---|:---|
| 1 | 進行中 | 837 筆，皆有未完成關卡 |
| 3 | 已結案 | 523,504 筆，關卡全數完成 |
| 4 | 已作廢 | 17,764 筆，其中 17,719 筆有 `abortComment` 與 `abortedManOID` |
| 5 | 已終止 | 10,330 筆，最後一個關卡的 `WorkItem` 也是 5 |

`WorkItem.currentState` 的 3（已完成）/ 4（已作廢）/ 5（已終止）有完成時間分佈佐證；
**0（待簽收）／1（處理中）／2（暫停）信心較低**，是由「未完成且屬於進行中流程」
加上 `acceptWorkItem` 必須先於 `completeWorkItem` 的順序推得。
未列出的代碼一律顯示成「狀態代碼 N」，不編造名稱。

## 驗證

```bash
cd 7_proc_export/backend && python -m pytest tests -q
```

17 項，涵蓋表單 XML 解析（含 FormCollection 包裝、表格明細、label 屬性）、
表格欄位標題、日期區間、狀態代碼、自訂條件比對、Excel 產出（工作表組成、
欄位標題、同名欄位加註 ID、控制字元）與表單關聯 SQL 的結構。**不需要資料庫**。

會連資料庫的路徑（`catalog` / `query`）沒放進自動測試 —— 那要有 `.env` 與內網。
改到那兩個模組時，實際跑一次前端：挑一支流程、查詢、點開一張單、匯出並打開 Excel。
