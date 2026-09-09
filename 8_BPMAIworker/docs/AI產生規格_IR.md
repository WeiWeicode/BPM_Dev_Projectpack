# AI 產生規格（IR，Intent Representation）

> **AI 只輸出這個格式，不輸出 XML。**
> 理由見 [../README.md](../README.md) 第 2 節：XStream 連號 id、32 碼 OID、
> 二次逃脫 XML 這三件事，LLM 逐字生成必然出錯且錯了不報錯。

IR 是「人講的需求」與「鼎新的檔案格式」之間唯一的介面。
它刻意只描述**業務意圖**，不描述樣式、座標、色彩、OID 與任何樣板值。

---

## 1. 兩份檔案

| 檔案 | 對應產出 |
|:---|:---|
| `form_ir.json` | `.form` + `.js` |
| `process_ir.json` | `.bpmn`（含各關卡欄位權限） |

分開的原因跟鼎新本身一致：一張表單可被多支流程引用，
權限屬於「關卡 × 欄位」而不屬於表單。

---

## 2. form_ir.json

```jsonc
{
  "irVersion": 1,
  "formId": "SolarEnergyECRECN",        // 英文，^[A-Za-z_][A-Za-z0-9_]*$
  "formName": "太陽能ECRECN 確認單(碩禾)", // 中文，設計師清單上看到的名字
  "fields": [
    {
      "id": "ECRNoTextBox",             // 英文識別字，全表單唯一
      "label": "ECR 單號",               // 中文顯示名稱；產生時會生出配對的 Label 元件
      "type": "TEXTBOX",                // 見第 4 節型別表
      "required": false,
      "hint": "",                       // 滑鼠提示，可省略
      "layout": { "row": 3, "col": 1, "span": 3 }  // 見第 5 節版面
    },
    {
      "id": "ChgPropertyRadio",
      "label": "變更屬性",
      "type": "RADIO",
      "options": [                      // SELECT / RADIO / CHECKBOX / DROPDOWN 專用
        { "value": "A", "caption": "設計變更" },
        { "value": "B", "caption": "製程變更" }
      ],
      "layout": { "row": 4, "col": 1, "span": 6 }
    },
    {
      "id": "ExtraDataGrid",
      "label": "附加資料明細",
      "type": "LIST",
      "columns": [                      // LIST（表格）專用；caption 是設計師實填的欄位標題
        { "id": "ItemNo",   "caption": "項次",   "type": "TEXTBOX" },
        { "id": "ItemDesc", "caption": "說明",   "type": "TEXTAREA" }
      ],
      "buttons": { "add": true, "update": true, "delete": true },
      "layout": { "row": 8, "col": 1, "span": 12 }
    }
  ],
  "script": {
    "hooks": ["formOpen", "formSave"],  // 要產生哪些生命週期函式的骨架
    "events": [                          // 要產生哪些事件函式的空殼
      { "field": "ChgItemDropDown", "event": "onchange" }
    ],
    "libs": ["EFGPShareMethod", "ajax_DatabaseAccessor"]  // 見表單腳本手冊
  }
}
```

### 必填 / 選填

| 欄位 | 必填 | 說明 |
|:---|:---:|:---|
| `formId` | ✅ | 匯入後即為 `FormDefinition.id`，也是權限字串裡的第一層標籤名 |
| `formName` | ✅ | 只用於顯示 |
| `fields[].id` | ✅ | **這是流程權限要引用的鍵，訂錯要改兩個檔** |
| `fields[].label` | ✅ | 空字串會導致產出的表單只看得到 ID（見 7_proc_export 的實測：舊表單 45% 沒填標籤，稽核時很痛苦） |
| `fields[].type` | ✅ | — |
| `layout` | ⭕ | 省略時依 `fields` 順序每列一個元件 |
| `options` | 型別相關 | `SELECT`／`RADIO`／`CHECKBOX`／`DROPDOWN` 必填 |
| `columns` | 型別相關 | `LIST` 必填 |

---

## 3. process_ir.json

```jsonc
{
  "irVersion": 1,
  "packageId": "GSRNProess",            // 流程包 ID
  "processId": "GSRNProess",            // 通常與 packageId 相同
  "processName": "太陽能 ECRECN 確認單(碩禾)",
  "formId": "SolarEnergyECRECN",        // 這支流程綁哪張表單（寫進 relevantDataDefinitions）
  "activities": [
    {
      "id": "StartEvent_1",
      "name": "",
      "type": "StartEvent"
    },
    {
      "id": "IssueECNReqUserTask",
      "name": "申請使用者填單",
      "type": "UserTask",
      "participant": "PROCESS_REQUESTER",   // 見第 6 節
      "permissions": {                       // 只列出「可編輯」的；沒列到的＝唯讀
        "ECRNoTextBox": "ENABLED",
        "ChgPropertyRadio": "ENABLED",
        "ExtraDataAddButton": "ENABLED"
      }
    },
    {
      "id": "ApplicantMgrUserTask",
      "name": "使用者直屬主管簽核",
      "type": "UserTask",
      "participant": "MANAGER",
      "permissions": { "ECSubjectTextBox": "ENABLED" }
    },
    {
      "id": "ApplySendTask",
      "name": "立案申請通知",
      "type": "SendTask"
    },
    { "id": "EndEvent_2", "name": "", "type": "EndEvent" }
  ],
  "transitions": [
    { "from": "StartEvent_1",          "to": "IssueECNReqUserTask" },
    { "from": "IssueECNReqUserTask",   "to": "ApplicantMgrUserTask" },
    { "from": "ApplicantMgrUserTask",  "to": "ApplySendTask" },
    { "from": "ApplySendTask",         "to": "EndEvent_2" }
  ]
}
```

### 權限的寫法（最容易錯的一格）

- **只寫要開放的欄位**。`ENABLED` 以外的三種狀態：
  | 想要的效果 | IR 怎麼寫 |
  |:---|:---|
  | 可編輯 | `"欄位ID": "ENABLED"` |
  | **唯讀** | **完全不要列出這個欄位** |
  | 隱藏 | `"欄位ID": "INVISIBLE"` |
  | 完全控制 | `"欄位ID": "FULL_CONTROL"`（極罕見，取樣佔比 0.2%） |
- **不要發明 `READ_ONLY` / `HIDDEN` / `DISABLED`**，資料庫實測只有上面三種值。
- 按鈕與欄位寫在同一個 `permissions` 字典裡（鼎新本身就不分），
  組裝器依 ID 結尾是否為 `Button` / `Btn` 自行歸類。
- `permissions` 內的每一個 key **必須存在於 `form_ir.json` 的 `fields[].id`**，
  校驗階段會擋下不存在的欄位——這正是 `5_ws_explorer` 手冊記載的
  「`invokeProcess` 不驗證欄位 id，錯的欄位靜默寫入、之後讀取才炸」的同型地雷。

---

## 4. 元件型別表

型別字串直接沿用 `1_xml_tool/core/form_handler.py` 萃取出來的值，
確保「產生 → 反解」對得起來。以下 27 種來自 `快速開發測試` 這支教材表單的實測：

| IR `type` | 鼎新元件類別 | 說明 |
|:---|:---|:---|
| `TEXTBOX` | `InputElementDefinition` (`INPUT_TYPE`) | 單行輸入 |
| `TEXTAREA` | `InputElementDefinition` (`INPUT_TEXTAREA_TYPE`) | 多行輸入 |
| `PASSWORD` | `InputElementDefinition` (`INPUT_PASSWORD_TYPE`) | 密碼 |
| `HIDDEN` | `InputElementDefinition` (`HIDDEN_TYPE`) | 隱藏欄，存流程實例 ID 等 |
| `RADIO` | `SelectElementDefinition` (`SELECT_RADIO_TYPE`) | 單選 |
| `CHECKBOX` | `SelectElementDefinition` (`SELECT_CHECKBOX_TYPE`) | 複選 |
| `DROPDOWN` | `SelectElementDefinition` (`SELECT_LIST_TYPE`) | 列表 |
| `SELECT` | `SelectElementDefinition` | 下拉 |
| `DATE` | `DateElementDefinition` (`DIALOG_DATE`) | 日期 |
| `DATETIME` | `DateElementDefinition` (`DIALOG_DATETIME`) | 日期時間 |
| `TIME` | `DateElementDefinition` (`DIALOG_TIME`) | 時間 |
| `BUTTON` | `TriggerElementDefinition` | 按鈕，中文名取 `caption` |
| `SERIAL_NUMBER` | `SerialNumberElementDefinition` | 單號 |
| `LIST` | `ListElementDefinition` | 表格明細 |
| `SUBTAB` | `SubTabElementDefinition` | 分頁 |
| `TITLE` | `TitleElementDefinition` | 標題 |
| `LABEL` | `OutputElementDefinition` | 純文字（也是所有欄位的中文標籤來源） |
| `HORIZONTAL_LINE` | `HorizontalLineElementDefinition` | 分隔線 |
| `IMAGE` | `ImageElementDefinition` | 圖片 |
| `ATTACHMENT` | `AttachmentElementDefinition` | 附件 |
| `LINK` / `BARCODE` / `QRCODE` / `HANDWRITING` | 各自的 ElementDefinition | 連結／條碼／QR／手寫 |
| `DIALOGINPUT` / `DIALOGINPUTLABEL` / `DIALOGINPUTMULTI` / `DOUBLETEXT` | 對話輸入系列 | 按鈕＋輸入框的組合元件 |

> ⚠️ `快速開發測試` 的 JSON 裡有兩處型別看起來像對調（`CheckBox16` → `SELECT`、
> `ListBox18` → `DROPDOWN`）。那是 `controlType` 的實際值造成的，不是筆誤；
> 產生時以本表為準，並在 M1 的往返測試中確認。

---

## 5. 版面（`layout`）

鼎新的 `rwdLayout` 是一段**逃脫過的 JSON**，本質是 12 欄格線：

```json
{"row":[3,3,3,3],"column":[[12],[12],[12],[12]],
 "elements":[[{"id":"TextBox5"}],[{"id":"TextArea6"}],[{"id":"SerialNumber9"}],[{}]]}
```

IR 只描述人看得懂的部分，其餘由組裝器換算：

| IR 欄位 | 意思 |
|:---|:---|
| `row` | 第幾列（1 起算） |
| `col` | 該列的第幾格（1 起算） |
| `span` | 佔幾欄（12 為滿版；4 欄並排就是每個 `span:3`） |

規則：
- 同一 `row` 的 `span` 加總不得超過 12。
- `TITLE`、`HORIZONTAL_LINE` 是整列型（`rowType`），不需要 `col` / `span`。
- 沒填 `layout` 的欄位一律排在最後，每列一個、`span:12`。

---

## 6. 執行者（`participant`）

`ParticipantDefinition.type` 的值，**不要照名稱猜語意**（AGENTS.md 第 1 節的提醒）：

| 值 | 意思 |
|:---|:---|
| `PROCESS_REQUESTER` | 流程申請人本人 |
| `MANAGER` | 申請人的直屬主管 |
| （其他值） | ⚠️ 尚未盤點完整。需要時用 `3_db_explorer` 查 `ParticipantDefinition.participantType` 的實際分布，不要自行編造。 |

---

## 7. 命名規範（給 AI 的硬規則）

| 對象 | 規則 | 例 |
|:---|:---|:---|
| 欄位 ID | 英文 PascalCase + **型別後綴** | `ECRNoTextBox`、`OnlineDate`、`ChgItemDropDown` |
| 按鈕 ID | 必須以 `Button` 或 `Btn` 結尾 | `ExtraDataAddButton` |
| 關卡 ID | 語意 + `UserTask` / `SendTask` 後綴 | `ApplicantMgrUserTask`、`ApplySendTask` |
| 隱藏欄 | 以 `Hidden` 結尾 | `processInstOIDHidden` |
| 表格明細 | 以 `Grid` 或 `List` 結尾 | `ExtraDataGrid` |

**按鈕後綴是有功能意義的**，不只是美觀：`bpmn_handler` 依 ID 結尾把權限項分成
「按鈕」與「欄位」兩區（`BUTTON_SUFFIXES = ('button', 'btn')`）。
按鈕沒有這個後綴，會被歸類成欄位，權限矩陣就對不上。

所有 ID 一律符合 `^[A-Za-z_][A-Za-z0-9_]*$`——這是 ①② 兩個工具共同的檢查式，
因為 ID 會被當成 XML 標籤名寫進 `formFieldAccessControl`。**中文、空白、減號一律不行。**
