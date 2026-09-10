# 範本清冊

新專案一律**從這裡複製再改**，不要憑空生成 XML。
理由見 [../README.md](../README.md) 第 2 節：XStream 連號 id、32 碼 OID、二次逃脫的權限字串，
LLM 逐字生成必然在某一格出錯，而且錯了不報錯，是匯入時才炸。

---

## 原始空白專案（目前唯一的基底）

```
原始空白專案/
├── 表單/OriginalBlankFormProject.form      2.5 KB、18 個 XStream 節點、0 個元件
└── 流程/OriginalBlankProcessProject.bpmn   62 KB、4 個關卡、42 個 OID
```

由鼎新設計器**直接匯出的空白專案**，沒有任何業務內容，是目前最乾淨的基底。

### 流程長相 —— 剛好就是最常見的三段簽核

```
StartEvent_1 ──▶ UserTask_3 ──▶ UserTask_4 ──▶ EndEvent_2
                 (人員任務)      (人員任務)
                 PROCESS_REQUESTER  MANAGER
```

**執行者已經設好了**：`UserTask_3` 掛 `PROCESS_REQUESTER`（流程申請人）、
`UserTask_4` 掛 `MANAGER`（申請人的直屬主管）。這是最省事的一點 ——
`ParticipantDefinition.type` 的完整值域我們還沒盤點完，能直接沿用就別自己編。

### 裡面已經有的東西

| 項目 | 狀態 |
|:---|:---|
| 起訖節點與兩個人員關卡 | ✅ 已連線（Link_5 / Link_6 / Link_7） |
| 執行者（申請人／主管） | ✅ 已設定 |
| 表單繫結 | ✅ `RelevantDataDefinition`（`FormType`）＋ `formDefinitionId` ＋ `relevantDataDefinitionId` 四處都在 |
| 開表單的 WebApplication | ✅ `CallFormHandler.do` 與 `CallAttachmentHandler.do` 兩支 |
| 流程圖 `bpmXML` | ✅ 4 節點 3 連線 |
| 表單骨架 | ✅ `formDefinitionStyles`、`rwdLayout` = `[]`、`script` 已含 5 個生命週期函式 |

### 裡面**沒有**的東西（複製後一定要自己補）

| 缺什麼 | 影響 | 補的方式 |
|:---|:---|:---|
| **`<formFieldAccessControl>`** | 兩個 UserTask 只有 `<formFieldAccessDefinition>` 空殼。這代表「沿用表單預設權限」，**關卡之間不會有任何差異** | `tools/set_permissions.py`（會在 `formFieldAccessDefinition` 內插一個進去） |
| 表單元件 | 表單是完全空白的，`elementDefinitions` 與 `rwdLayout` 都空 | 目前只能從別的表單複製元件段落再重編號（`tools/bpm_edit.py` 的 `inline_numeric_refs` + `renumber_form_ids`） |
| 業務腳本 | `script` 只有 5 個 `return true` 的空函式 | 改 `.js` 再由組裝流程寫回 |

---

## 怎麼用

```bash
python 8_BPMAIworker/tools/new_project.py --name 採購申請單 --form-id PurchaseForm --process-id PurchaseProcess
```

複製時只換掉「識別身分」的那幾格，其餘一個位元組都不動：

| 換掉的 | 範本值 → 新值 |
|:---|:---|
| 表單 `<id>` / `<name>` | `OriginalBlankFormProject` → `PurchaseForm` / 中文名 |
| 流程包與流程定義 `<id>` / `<name>` / `<mainProcessDefinitionId>` | `OriginalBlankProcessProject` / `原始空白流程專案` → 新值 |
| 表單繫結 4 處 | `formDefinitionId`、`relevantDataDefinitionId`、`RelevantDataDefinition` 的 `<id>` 與 `<name>` |
| 關卡 ID 與中文名 | `UserTask_3` → `ApplyUserTask`（開單人）、`UserTask_4` → `ManagerUserTask`（直屬主管） |
| 流程圖節點文字 | 認 `Node Id` 再改，**不能照出現順序改**——兩個 UserTask 的預設文字都是「人員任務」 |
| 全部 OID | 依 `form-id + process-id` 的雜湊分配區段，每個專案 256 個號，不同專案不會撞號 |

關卡 ID 與中文名可用 `--apply-id` / `--manager-id` / `--apply-name` / `--manager-name` 改。

複製完會自動檢查：XML 合法、範本識別字有沒有殘留、所有 `reference` 解析得到、關卡是否改名成功。

---

## 為什麼保留一份在 `samples/` 之外

`samples/` 裡的是實際工作目錄，會被增刪；`templates/` 這份是**基準**，
只有在鼎新改版、需要重新從設計器匯出一份新的空白專案時才更新。

> 注意：`.gitignore` 目前只擋 `/samples/*.form`、`/samples/*.bpmn`、`/samples/*.json`
> ——**只擋 samples 根目錄下的檔案，不擋子資料夾**。這份範本放在 `8_BPMAIworker/templates/`
> 會進版控；它本身沒有任何業務內容，只有結構骨架與一組 OID，所以沒問題。
