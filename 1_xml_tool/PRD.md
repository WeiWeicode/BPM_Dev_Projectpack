# 產品需求文件 (PRD)：鼎新 BPM XML 雙向處理工具 (BPM XML Sync Tool)

---

## 1. 執行摘要 (Executive Summary)

### 1.1 專案背景
鼎新電腦 (DSC Nana BPM) 系統所產出的表單定義檔（`.form`）與流程定義檔（`.bpmn`）為高度複雜且深層嵌套的 Java 序列化 XML 檔案。
在 BPM 快速開發流程中，開發人員經常需要批次重新命名元件 ID（Field ID）或關卡 ID（Activity ID）以符合專案命名規範。手動在龐大的 XML 中尋找與替換 ID 容易出錯，且容易破壞 XML 結構與關聯參照。

### 1.2 產品目標
本工具使用 **Python** 開發，提供簡潔友善的 **Terminal 終端互動視窗（Interactive CLI Menu）**，提供兩大核心功能：
1. **功能一【匯出 XML 轉 JSON】**：
   - **Form 萃取**：解析 `.form`，以「中文名稱」為識別依據，萃取出欄位 ID 與中文名稱（主動排除所有 JavaScript 與多餘樣式）。
   - **BPMN 萃取**：解析 `.bpmn`，萃取各關卡名稱、關卡 ID 以及按鈕/欄位存取權限。
2. **功能二【匯入 JSON 回寫 XML】**：
   - 使用者在產出的 JSON 中直接修改 ID。
   - **Form 回寫**：以**中文名稱**為鍵值（Key），精準尋找對應元件並更新其 ID，連動更新相關 Label 標籤 ID。
   - **BPMN 回寫**：以**關卡中文名稱**為鍵值（Key），更新關卡 ID，並自動同步更新流程圖節點（`bpmXML`）、連線（`DiagramLink`）及參與者定義中的關聯 ID。
   - **輸出命名規格**：自動另存為 `已完成_[原檔名].form` 或 `已完成_[原檔名].bpmn`，絕不覆蓋原檔。

---

## 2. 系統架構與互動流程 (Architecture & Workflow)

```mermaid
graph TD
    A[Terminal 互動選單] -->|選擇 1| B[功能一: 匯出 XML 轉 JSON]
    A -->|選擇 2| C[功能二: 匯入 JSON 回寫 XML]
    A -->|選擇 0| D[離開系統]

    subgraph 匯出流程 (Export)
        B --> B1[選取 .form / .bpmn 檔案]
        B1 --> B2[解析 XML 結構與中文字元]
        B2 --> B3[過濾 JS / 樣式 / 代理標籤]
        B3 --> B4[輸出 .json 設定檔]
    end

    subgraph 人工編輯 (Edit)
        B4 -.->|開發人員修改 JSON 內的 ID| C1[已編輯的 .json]
    end

    subgraph 回寫流程 (Write-back)
        C --> C1
        C1 --> C2[以「中文名稱」為 Key 進行匹配]
        C2 --> C3[替換 XML 中的 ID 與關聯參照]
        C3 --> C4[輸出「已完成_檔名.form / bpmn」]
    end
```

---

## 3. 詳細功能規格 (Functional Specifications)

### 3.1 功能一：匯出 XML 轉 JSON (XML to JSON Extraction)

#### (1) 表單檔案 (`.form`) 萃取規格
- **萃取邏輯**：
  - 識別 `<elementDefinitions>` 底下所有控制項（`InputElementDefinition`, `DateElementDefinition`, `SelectElementDefinition`, `TriggerElementDefinition`, `SerialNumberElementDefinition` 等）。
  - 自動透過 `pairId` 或 `lbl_{元件ID}` 關聯配對標籤（`OutputElementDefinition` 的 `textValue`）以取得中文名稱。
  - 按鈕類別（`TriggerElementDefinition`）直接抓取 `caption` 或 `id` 作為中文名稱。
- **過濾原則**：
  - ❌ **完全排除 JavaScript 程式碼**（不輸出 `<script>`、驗證規則腳本）。
  - ❌ 排除 CSS 樣式字串、座標（`coordinateX`, `coordinateY`）、色彩設定、字型等。
- **輸出 JSON 規格**：
  以清晰的結構記錄「中文名稱（作為 Key/主要識別）」與「目前 ID」，方便後續人工修改：
  ```json
  {
    "fileType": "FORM",
    "formId": "SP_DetectionOPForm",
    "fields": [
      {
        "name": "管制計畫編號",
        "id": "ControlPlanNoTextBox",
        "type": "TEXTBOX"
      },
      {
        "name": "產品品名",
        "id": "ControlPlanProductTextBox",
        "type": "TEXTBOX"
      },
      {
        "name": "管制計畫申請日期",
        "id": "ControlPlanApplyDate",
        "type": "DATE"
      },
      {
        "name": "匯入CP",
        "id": "ImportCPButton",
        "type": "BUTTON"
      },
      {
        "name": "上傳檔案",
        "id": "UploadFileButton",
        "type": "BUTTON"
      },
      {
        "name": "是否設定失效文件",
        "id": "JudgeSaveWebAppRadio",
        "type": "RADIO"
      }
    ]
  }
  ```

---

#### (2) 流程檔案 (`.bpmn`) 萃取規格
- **萃取邏輯**：
  - 識別 `<processDefinitions>` -> `<activityDefinitions>` 中所有活動節點。
  - 萃取 **關卡名稱（`<name>`）**、**關卡 ID（`<id>`）**、**節點類型（`<bpmnType>`）**。
  - 深入解析 `<formFieldAccessControl>` 內嵌的 XML 字串，萃取該關卡各按鈕與欄位的權限狀態（如 `ENABLED`）。
- **輸出 JSON 規格**：
  ```json
  {
    "fileType": "BPMN",
    "processId": "SP_DetectionOPProcess",
    "processName": "特用膠材 管制計畫(CP)",
    "activities": [
      {
        "name": "發起人",
        "id": "InitiatorTask",
        "type": "UserTask",
        "buttons": [
          { "id": "testButton", "permission": "ENABLED" },
          { "id": "ImportCPButton", "permission": "ENABLED" },
          { "id": "UploadFileButton", "permission": "ENABLED" }
        ],
        "fieldPermissions": {
          "ControlPlanNoTextBox": "ENABLED",
          "ControlPlanProductTextBox": "ENABLED",
          "ControlPlanEditionNoTextBox": "ENABLED",
          "ControlPlanApplyDate": "ENABLED"
        }
      },
      {
        "name": "發起人主管",
        "id": "InitatorManagerTask",
        "type": "UserTask",
        "buttons": [],
        "fieldPermissions": {}
      },
      {
        "name": "發起人設定失效文件與發送mail",
        "id": "InitiatorSaveWebAppTask",
        "type": "UserTask",
        "buttons": [
          { "id": "SelectExpiredButton", "permission": "ENABLED" },
          { "id": "CancelExpiredButton", "permission": "ENABLED" }
        ],
        "fieldPermissions": {
          "JudgeSaveWebAppRadio": "ENABLED",
          "MailTitleTextBox": "ENABLED"
        }
      }
    ]
  }
  ```

---

### 3.2 功能二：匯入 JSON 回寫 XML (JSON to XML Write-back)

#### (1) 表單回寫機制 (`.form`)
- **比對鍵值**：以 JSON 中每個項目的 **`originalId`** 作為查找 Key。
- **替換標的**：
  1. 尋找對應的控制項節點，將控制項的 `<id>` 與 `<name>` 節點值更新為 JSON 中指定的新 `id`。
  2. 若有對應的標籤（Label），同步將標籤的 `<id>`、`<name>` 更新為 `lbl_{新ID}`。
  3. **RWD 版面配置 (`<rwdLayout>`)**：同步將版面 JSON 中的元件 ID 參照更新為新 ID，避免 BPM Web 設計器拋出 `TypeError: Cannot read properties of null (reading 'type')`。
  4. **表單腳本 (`<script>` / `<mobileScript>`)**：同步更新表格事件函式名稱（如 `${GridId}_add_onclick`）與物件變數（如 `${GridId}Obj`）。
- **輸出檔名規則**：
  - 範例：若來源為 `SP_DetectionOPForm.form`，回寫輸出檔名為 `已完成_SP_DetectionOPForm.form`。

---

#### (2) 流程回寫機制 (`.bpmn`)
- **比對鍵值**：以 JSON 中每個活動的 **`name`（關卡中文名稱）** 作為查找 Key。
- **連動更新範圍**（確保流程圖與引擎參照不損壞）：
  1. **活動定義節點**：將 `<ActivityDefinition>` 中的 `<id>` 更新為新 ID。
  2. **流程圖 XML 節點 (`<bpmXML>`)**：
     - `<Node ClassName="..." Id="[舊ID]">` ➔ 更新為 `Id="[新ID]"`
     - `<ContainerNode NodeId="[舊ID]">` ➔ 更新為 `NodeId="[新ID]"`
     - `<DiagramLink>` 中的 `<Form Id="[舊ID]">` 與 `<To Id="[舊ID]">` ➔ 更新為新 ID
  3. **參與者關聯**：若 `<ParticipantDefinition>` 內有 `<activityDefinitionId>[舊ID]</activityDefinitionId>`，同步替換為新 ID。
  4. **表單欄位權限**：若 JSON 中同步修改了關卡內的按鈕/欄位 ID，同步更新 `<formFieldAccessControl>` 內部的 XML 標籤名稱。
- **輸出檔名規則**：
  - 範例：若來源為 `特用膠材 管制計畫(CP).bpmn`，回寫輸出檔名為 `已完成_特用膠材 管制計畫(CP).bpmn`。

---

## 4. Terminal 互動視窗設計 (CLI Interactive Menu)

啟動指令：`python bpm_tool.py`

### 4.1 主選單介面
```text
============================================================
           鼎新 BPM XML 雙向處理工具 (Python)
============================================================
 [1] 匯出 XML 轉 JSON (Extract)
     - 解析 .form / .bpmn 檔案，萃取 ID、中文名稱與按鈕權限
 [2] 匯入 JSON 回寫 XML (Write-back)
     - 依「中文名稱」鍵值更新 ID，另存為「已完成_檔名」
 [0] 離開系統
============================================================
請選擇功能項目 [0-2]: 
```

### 4.2 功能 [1] 匯出互動流程範例
```text
>>> 搜尋目錄下支援的 XML 檔案...
 [1] SP_DetectionOPForm.form (表單)
 [2] 特用膠材 管制計畫(CP).bpmn (流程)
 [A] 全部轉換

請選擇要匯出的檔案: 1
正在解析 SP_DetectionOPForm.form...
✔ 成功萃取 24 個欄位 (已排除 JavaScript 與樣式)
✔ 已產出 JSON 檔案: SP_DetectionOPForm.json
```

### 4.3 功能 [2] 回寫互動流程範例
```text
>>> 搜尋目錄下可用的 JSON 設定檔...
 [1] SP_DetectionOPForm.json
 [2] 特用膠材 管制計畫(CP).json

請選擇要回寫的 JSON 設定檔: 1
請確認要回寫的原始 XML 檔案 [預設: SP_DetectionOPForm.form]: 
正在以「中文名稱」為鍵值進行比對與 ID 替換...
✔ 成功比對並更新 24 個欄位 ID
✔ 已生成新檔案: 已完成_SP_DetectionOPForm.form

============================================================
更新成功！原始檔案未受影響。
============================================================
```

---

## 5. 技術規格與模組規劃 (Technical Specifications)

### 5.1 環境與依賴
- **語言**：Python 3.8+
- **依賴庫**：
  - `xml.etree.ElementTree`（內建標準庫，確保零外部依賴）
  - `json`, `os`, `re`, `html`（內建標準庫）
  - 編碼一律採用 **`UTF-8`**，並支援 XML 宣告頭寫入（`<?xml version="1.0" encoding="UTF-8"?>`）。

### 5.2 專案檔案結構
```text
BPM快速開發/
├── bpm_tool.py                  # 終端互動主程式 (Terminal CLI UI)
├── core/
│   ├── __init__.py
│   ├── form_handler.py          # 表單萃取與回寫模組
│   ├── bpmn_handler.py          # 流程萃取與回寫模組
│   └── xml_utils.py             # XML 讀寫、CDAT/轉義字串處理工具
├── PRD.md                       # 本產品需求文件
├── SP_DetectionOPForm.form      # 原始表單檔範例
└── 特用膠材 管制計畫(CP).bpmn   # 原始流程檔範例
```

---

## 6. 驗收標準 (Acceptance Criteria)

| 測試項目 | 驗收標準 |
| :--- | :--- |
| **互動選單** | 執行 `python bpm_tool.py` 能夠正常啟動互動終端視窗，包含功能 [1]、[2] 與 [0]。 |
| **Form 匯出** | 產出的 JSON 包含所有元件的中文名稱與原始 ID，且完全無 JavaScript 腳本。 |
| **BPMN 匯出** | 產出的 JSON 正確列出各關卡中文名稱、關卡 ID 以及按鈕權限矩陣。 |
| **Form 回寫** | 依據 JSON 中以「中文名稱」為鍵值修改的新 ID，成功生成 `已完成_xxx.form`，XML 結構完整可用。 |
| **BPMN 回寫** | 依據 JSON 中以「關卡中文名稱」為鍵值修改的新 ID，成功更新 `ActivityDefinition`、`bpmXML` 圖形節點及 `DiagramLink` 連線，生成 `已完成_xxx.bpmn`。 |
| **檔案命名** | 回寫後的新檔案名稱一律嚴格遵循 `已完成_[原檔名].form` 或 `已完成_[原檔名].bpmn`。 |
