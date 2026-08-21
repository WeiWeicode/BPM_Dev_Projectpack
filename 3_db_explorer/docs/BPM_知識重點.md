# 鼎新 BPM 資料模型重點整理

> 由 `bpm_kb` 自動產生。資料來源：`sa@10.10.130.191,1433/NaNa`，範圍：近 7 天建立的版本。

## 1. 定義存在哪裡

| 資料表 | 欄位 | 內容 |
| --- | --- | --- |
| FormDefinition | defSerialize | 表單定義 XML —— 匯出的 `.form` 本體 |
| FormDefinition | script / mobileScript | 表單 JS，與 XML 分開存 |
| FormDefinition | rwdLayout | RWD 版面配置 |
| FormDefinition | multiZhMap | 多語系字串對照 |
| ProcessDefinition | bpmXML | **只有畫布座標**（Diagram / Node / Bounds），不含邏輯 |
| ActivityDefinition | （關聯欄位） | 關卡本體：名稱、執行方式、執行者 |
| TransitionDefinition | （關聯欄位） | 關卡之間的連線與條件 |
| FormFieldAccessDefinition | formFieldAccessControl | 每個關卡的欄位／按鈕權限 |
| ParticipantDefinition | （關聯欄位） | 執行者定義（簽核對象怎麼算） |
| （多張表） | bundleContainer | 多語系資源包，不是定義本體 |

> 關鍵差異：**表單是整份 XML 存一格，流程是拆進關聯表**。
> 匯出的 `.bpmn` 檔是設計師把關聯表重新序列化出來的結果，
> 資料庫裡並沒有一個欄位長得跟它一樣。

探索器實際抽樣到的 `com.dsc.*` 序列化欄位：

| 資料表 | 欄位 | Java 類別 | 筆數 |
| --- | --- | --- | --- |
| LocalNoticeWorkItem | bundleContainer | com.dsc.nana.domain.XMLRsrcBundleContainerImpl | 905007 |
| ProcessInstance | bundleContainer | com.dsc.nana.domain.XMLRsrcBundleContainerImpl | 552396 |
| ProcessDefinition | bundleContainer | com.dsc.nana.domain.XMLRsrcBundleContainerImpl | 329849 |
| ProcessPackage | bundleContainer | com.dsc.nana.domain.XMLRsrcBundleContainerImpl | 7179 |
| FormDefinition | defSerialize | com.dsc.nana.domain.form.FormDefinition | 2848 |
| LocalToDoWorkItem | bundleContainer | com.dsc.nana.domain.XMLRsrcBundleContainerImpl | 1368 |
| PrsInsLvl | bundleContainer | com.dsc.nana.domain.XMLRsrcBundleContainerImpl | 3 |
| AuthorityScope | bundleContainer | com.dsc.nana.domain.XMLRsrcBundleContainerImpl | 2 |
| TiptopModel | mappingSet | com.dsc.nana.domain.sysintegration.tiptop.model.TiptopProcessMapping | 1 |

## 2. 版本怎麼運作

### 表單：版本欄位就在 FormDefinition 自己身上

同一個 `id` 有多筆記錄，`version` 遞增；`containerOID` 是表單的邏輯身分，
同一張表單的各版本共用同一個 `containerOID`。`publicationStatus` 為
`RELEASED`（已發佈）或 `UNDER_REVISION`（修訂中），`validFrom` / `validTo`
決定生效區間。`objectVersion` 是 O/R mapping 的樂觀鎖，與表單版本無關。

### 流程：版本資訊拆在 header 表

```
ProcessPackage                     流程套件，一個版本一筆
 ├─ headerOID            → ProcessPackageHeader   createdTime / bpmnVersion
 ├─ redefinableHeaderOID → RedefinableHeader      version / publicationStatus
 └─ OID → ProcessPackage_ProcessDef → ProcessDefinition
                                       OID 即各關聯表的 containerOID
                                       bpmXML = 畫布座標

ProcessDefinition.OID = containerOID 之下掛：
   ActivityDefinition        關卡
   TransitionDefinition      連線（from / to）
   ParticipantDefinition     執行者
```

要重建一份流程，必須用 `containerOID` 把這幾張表撈齊 —— 這正是
`bpm_kb/process_graph.py` 在做的事。

## 3. 目前有哪些表單與流程

### 表單（近 7 天建立的版本）

| id | formDefinitionName | version | publicationStatus | createdTime | xml_chars |
| --- | --- | --- | --- | --- | --- |
| quickDevTestFormImport | 快速開發測試 | 1 | RELEASED | 2026-08-20 14:57:29.130000 | 219670 |
| quickDevTestForm | 快速開發測試 | 2 | RELEASED | 2026-08-20 14:22:35.203000 | 218933 |
| quickDevTestForm | quickDevTestForm | 1 | UNDER_REVISION | 2026-08-20 14:22:09.953000 | 218671 |

### 流程（近 7 天建立的版本）

| id | processPackageName | version | publicationStatus | createdTime | flowType |
| --- | --- | --- | --- | --- | --- |
| quickDevTestProcessImportWebTool | 測試快速開發(webTool) | 2 | RELEASED | 2026-08-20 15:54:18 | SignatureFlow |
| quickDevTestProcessImport | 測試快速開發 | 3 | RELEASED | 2026-08-20 15:06:01 | SignatureFlow |
| quickDevTestProcessImportWebTool | 測試快速開發 | 1 | UNDER_REVISION | 2026-08-20 15:06:01 | SignatureFlow |
| quickDevTestProcessImport | 測試快速開發 | 2 | UNDER_REVISION | 2026-08-20 14:43:43 | SignatureFlow |
| quickDevTestProcessImport | 測試快速開發 | 1 | UNDER_REVISION | 2026-08-20 14:26:58 | SignatureFlow |

## 4. 表單與流程如何扣在一起

兩者之間沒有外鍵。關聯落在 `ActivityDefinition.formFieldAccessDefinitionOID`
→ `FormFieldAccessDefinition.formFieldAccessControl`，內容是一段
`<FormFieldAccessControl><表單ID><欄位ID>權限</欄位ID>…</表單ID></FormFieldAccessControl>`。
所以「表單掛在哪個關卡」與「該關卡看得到什麼」是同一筆資料決定的。

#### quickDevTestProcessImportWebTool v1　測試快速開發（SignatureFlow，UNDER_REVISION）

`ACT_Start_03 → ACT_CreateForm_06 → ACT_ManagerApprove_02 → ACT_SendNotify_01 → ACT_ManualTask_05 → ACT_End_04`

| 關卡 ID | 名稱 | BPMN 型別 | 執行方式 | 執行者 | 表單 | 欄位權限 | 按鈕數 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACT_Start_03 | Event | StartEvent | NORMAL | - | - | - | 0 |
| ACT_CreateForm_06 | 開單 | UserTask | NORMAL | PROCESS_REQUESTER | quickDevTestFormImport | ENABLED×14 | 1 |
| ACT_ManagerApprove_02 | 主管 | UserTask | NORMAL | MANAGER | quickDevTestFormImport | ENABLED×10 | 1 |
| ACT_SendNotify_01 | 通知任務 | SendTask | NOTICE | PROCESS_REQUESTER | - | - | 0 |
| ACT_ManualTask_05 | 人工任務 | ManualTask | NORMAL | PROCESS_REQUESTER | quickDevTestFormImport | ENABLED×4 | 0 |
| ACT_End_04 | Event | EndEvent | NORMAL | - | - | - | 0 |

#### quickDevTestProcessImportWebTool v2　測試快速開發(webTool)（SignatureFlow，RELEASED）

`ACT_Start_03 → ACT_CreateForm_06 → ACT_ManagerApprove_02 → ACT_SendNotify_01 → ACT_ManualTask_05 → ACT_End_04`

| 關卡 ID | 名稱 | BPMN 型別 | 執行方式 | 執行者 | 表單 | 欄位權限 | 按鈕數 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACT_Start_03 | Event | StartEvent | NORMAL | - | - | - | 0 |
| ACT_CreateForm_06 | 開單 | UserTask | NORMAL | PROCESS_REQUESTER | quickDevTestFormImport | ENABLED×14 | 1 |
| ACT_ManagerApprove_02 | 主管 | UserTask | NORMAL | MANAGER | quickDevTestFormImport | ENABLED×10 | 1 |
| ACT_SendNotify_01 | 通知任務 | SendTask | NOTICE | PROCESS_REQUESTER | - | - | 0 |
| ACT_ManualTask_05 | 人工任務 | ManualTask | NORMAL | PROCESS_REQUESTER | quickDevTestFormImport | ENABLED×4 | 0 |
| ACT_End_04 | Event | EndEvent | NORMAL | - | - | - | 0 |

#### quickDevTestProcessImport v1　測試快速開發（SignatureFlow，UNDER_REVISION）

`ACT_Start_03 → ACT_CreateForm_06 → ACT_ManagerApprove_02 → ACT_SendNotify_01 → ACT_DecisionRule_07 → ACT_ManualTask_05 → ACT_End_04`

| 關卡 ID | 名稱 | BPMN 型別 | 執行方式 | 執行者 | 表單 | 欄位權限 | 按鈕數 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACT_Start_03 | Event | StartEvent | NORMAL | - | - | - | 0 |
| ACT_CreateForm_06 | 開單 | UserTask | NORMAL | PROCESS_REQUESTER | - | - | 0 |
| ACT_ManagerApprove_02 | 主管 | UserTask | NORMAL | MANAGER | - | - | 0 |
| ACT_SendNotify_01 | 通知任務 | SendTask | NOTICE | PROCESS_REQUESTER | - | - | 0 |
| ACT_DecisionRule_07 | 核決層級 | DecisionRuleTask | NORMAL | - | - | - | 0 |
| ACT_ManualTask_05 | 人工任務 | ManualTask | NORMAL | PROCESS_REQUESTER | - | - | 0 |
| ACT_End_04 | Event | EndEvent | NORMAL | - | - | - | 0 |

#### quickDevTestProcessImport v2　測試快速開發（SignatureFlow，UNDER_REVISION）

`ACT_Start_03 → ACT_CreateForm_06 → ACT_ManagerApprove_02 → ACT_SendNotify_01 → ACT_ManualTask_05 → ACT_End_04`

| 關卡 ID | 名稱 | BPMN 型別 | 執行方式 | 執行者 | 表單 | 欄位權限 | 按鈕數 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACT_Start_03 | Event | StartEvent | NORMAL | - | - | - | 0 |
| ACT_CreateForm_06 | 開單 | UserTask | NORMAL | PROCESS_REQUESTER | - | - | 0 |
| ACT_ManagerApprove_02 | 主管 | UserTask | NORMAL | MANAGER | - | - | 0 |
| ACT_SendNotify_01 | 通知任務 | SendTask | NOTICE | PROCESS_REQUESTER | - | - | 0 |
| ACT_ManualTask_05 | 人工任務 | ManualTask | NORMAL | PROCESS_REQUESTER | - | - | 0 |
| ACT_End_04 | Event | EndEvent | NORMAL | - | - | - | 0 |

#### quickDevTestProcessImport v3　測試快速開發（SignatureFlow，RELEASED）

`ACT_Start_03 → ACT_CreateForm_06 → ACT_ManagerApprove_02 → ACT_SendNotify_01 → ACT_ManualTask_05 → ACT_End_04`

| 關卡 ID | 名稱 | BPMN 型別 | 執行方式 | 執行者 | 表單 | 欄位權限 | 按鈕數 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACT_Start_03 | Event | StartEvent | NORMAL | - | - | - | 0 |
| ACT_CreateForm_06 | 開單 | UserTask | NORMAL | PROCESS_REQUESTER | quickDevTestFormImport | ENABLED×2 | 1 |
| ACT_ManagerApprove_02 | 主管 | UserTask | NORMAL | MANAGER | quickDevTestFormImport | ENABLED×1 | 0 |
| ACT_SendNotify_01 | 通知任務 | SendTask | NOTICE | PROCESS_REQUESTER | - | - | 0 |
| ACT_ManualTask_05 | 人工任務 | ManualTask | NORMAL | PROCESS_REQUESTER | quickDevTestFormImport | ENABLED×4 | 0 |
| ACT_End_04 | Event | EndEvent | NORMAL | - | - | - | 0 |

### 關卡 × 欄位權限矩陣

以 `quickDevTestProcessImportWebTool` v1 為例：

| 欄位 ID | 開單 | 主管 | 人工任務 |
| --- | --- | --- | --- |
| TEST_Attachment_05 | ENABLED | — | — |
| TEST_TextBox_07 | ENABLED | ENABLED | — |
| TEST_TextArea_08 | ENABLED | ENABLED | — |
| TEST_Grid_10 | ENABLED | — | — |
| TEST_DialogInput_11 | ENABLED | ENABLED | — |
| TEST_DialogInputLabel_12 | ENABLED | ENABLED | ENABLED |
| TEST_DialogInputMulti_13 | ENABLED | ENABLED | ENABLED |
| TEST_DoubleTextBox_14 | ENABLED | ENABLED | ENABLED |
| TEST_RadioButton_15 | ENABLED | ENABLED | — |
| TEST_CheckBox_16 | ENABLED | ENABLED | — |
| TEST_Dropdown_17 | ENABLED | ENABLED | ENABLED |
| TEST_Date_19 | ENABLED | — | — |
| TEST_Time_20 | ENABLED | — | — |
| TEST_HandWriting_28 | ENABLED | ENABLED | — |
| TEST_Button_06 | ENABLED | ENABLED | — |

權限值取自資料庫實測（取樣 4000 筆 FormFieldAccessDefinition）：
`ENABLED`（可編輯，絕大多數）、`INVISIBLE`（隱藏）、`FULL_CONTROL`（完全控制）。
未列出者以 `—` 表示，代表該關卡未設定、沿用表單預設。

### 表單欄位樣本

#### quickDevTestFormImport（快速開發測試，共 27 個元件）

| 元件 ID | 顯示名稱 | 型別 |
| --- | --- | --- |
| TEST_Hidden_01 | HiddenTextBox | HIDDEN |
| TEST_Title_02 | Title | TITLE |
| TEST_HorizontalLine_03 | 分隔線 | HORIZONTAL_LINE |
| TEST_Label_04 | 文本 | LABEL |
| TEST_Attachment_05 | 檔案上傳 | ATTACHMENT |
| TEST_Button_06 | 按鈕 | BUTTON |
| TEST_TextBox_07 | 輸入框 | TEXTBOX |
| TEST_TextArea_08 | 輸入區域 | TEXTAREA |
| TEST_SerialNumber_09 | 單號 | SERIAL_NUMBER |
| TEST_Grid_10 | 表格 | LIST |
| TEST_DialogInput_11 | 按鈕+輸入框 | DIALOGINPUT |
| TEST_DialogInputLabel_12 | 按鈕+雙輸入框 | DIALOGINPUTLABEL |
| TEST_DialogInputMulti_13 | 按鈕+輸入區域 | DIALOGINPUTMULTI |
| TEST_DoubleTextBox_14 | 雙輸入框 | DOUBLETEXT |
| TEST_RadioButton_15 | 選擇按鈕 | RADIO |
| TEST_CheckBox_16 | 複選按鈕 | SELECT |
| TEST_Dropdown_17 | 下拉選擇 | SELECT |
| TEST_ListBox_18 | 列表 | DROPDOWN |
| TEST_Date_19 | 日期 | DATE |
| TEST_Time_20 | 時間 | TIME |
| TEST_SubTab_22 | TEST_SubTab_22 | SUBTAB |
| TEST_Password_23 | 密碼 | TEXTBOX |
| TEST_Image_24 | TEST_Image_24 | IMAGE |
| TEST_Link_25 | 連結 | LINK |
| TEST_Barcode_26 | 條碼 | BARCODE |
| TEST_QRCode_27 | TEST_QRCode_27 | QRCODE |
| TEST_HandWriting_28 | 手寫區域 | HANDWRITING |

#### quickDevTestForm（quickDevTestForm，共 27 個元件）

| 元件 ID | 顯示名稱 | 型別 |
| --- | --- | --- |
| Title1 | Title | TITLE |
| HorizontalLine2 | 分隔線 | HORIZONTAL_LINE |
| Label3 | 文本 | LABEL |
| Button4 | 按鈕 | BUTTON |
| TextBox5 | 輸入框 | TEXTBOX |
| TextArea6 | 輸入區域 | TEXTAREA |
| HiddenTextBox7 | HiddenTextBox | HIDDEN |
| Attachment | 檔案上傳 | ATTACHMENT |
| SerialNumber9 | 單號 | SERIAL_NUMBER |
| Grid10 | 表格 | LIST |
| DialogInput11 | 按鈕+輸入框 | DIALOGINPUT |
| DialogInputLabel12 | 按鈕+雙輸入框 | DIALOGINPUTLABEL |
| DialogInputMulti13 | 按鈕+輸入區域 | DIALOGINPUTMULTI |
| DoubleTextBox14 | 雙輸入框 | DOUBLETEXT |
| RadioButton15 | 選擇按鈕 | RADIO |
| CheckBox16 | 複選按鈕 | SELECT |
| Dropdown17 | 下拉選擇 | SELECT |
| ListBox18 | 列表 | DROPDOWN |
| Date19 | 日期 | DATE |
| Time20 | 時間 | TIME |
| SubTab22 | SubTab22 | SUBTAB |
| Password23 | 密碼 | TEXTBOX |
| Image24 | Image24 | IMAGE |
| Link25 | 連結 | LINK |
| Barcode26 | 條碼 | BARCODE |
| QRCode27 | QRCode27 | QRCODE |
| HandWriting28 | 手寫區域 | HANDWRITING |

（另有 1 張表單，明細見 `out/forms/*.json`）

## 5. 資料表全景

| 資料表 | 筆數 |
| --- | --- |
| ChangeActivityStateAudit | 12372461 |
| ChangeWorkItemStateAudit | 8441029 |
| ActivityNotification | 5664974 |
| ArchiveProcessDetail | 4289248 |
| TransitionRestriction | 4279593 |
| ActivityDefinition | 4279592 |
| TransitionReference | 4258334 |
| TransitionDefinition | 4215520 |
| ParticipantDefinition | 3407343 |
| WorkItem | 3396683 |
| WorkStep | 3395619 |
| ParticipantActivityInstance | 3366211 |
| IAppDefContainer_AppDef | 3138781 |
| LocalRelevantData | 1818274 |
| StringWorkflowRuntimeValue | 1265883 |
| ChangeProcessStateAudit | 1098024 |
| RelevantDataDefinition | 1028097 |
| WorkAssignment | 1025839 |
| ActualParameter | 1009597 |
| Tool | 1006009 |
| LocalNoticeWorkItem | 905007 |
| LicenseStatRcd | 850172 |
| BoundViewInformation | 757477 |
| ProcessContext | 552396 |
| ProcessInstance | 552396 |
| FormInstance | 552381 |
| ProcessNotification | 550452 |
| BlockActivityInstance | 547015 |
| ActivitySetDefinition | 543350 |
| ProcessMappingKey | 404548 |
| ProcessDefinition | 329849 |
| ProcessPackage_ProcessDef | 329826 |
| CustomProcessPackage | 322646 |
| NoCmDocument | 208264 |
| DocServer_IDocument | 203580 |
| Implementation | 144509 |
| ReadingRecord | 142897 |
| BamActInstData | 133575 |
| FormOperationDefinition | 133547 |
| DeployedUnit | 132198 |

（僅列出筆數前 40 名，共 385 張有資料的表）
