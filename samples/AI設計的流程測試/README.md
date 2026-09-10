# AI設計的流程測試 —— 匯入與測試說明

由 `8_BPMAIworker/tools/` 產生，用來實測「AI 產生的表單與流程能不能匯入鼎新 BPM 並跑完」。

```
AI設計的流程測試/
├── 表單/
│   ├── AIDesignTestForm.form     ← 匯入表單設計器
│   ├── AIDesignTestForm.js       ← 表單腳本（已內嵌進 .form，這份是給人看的原始碼）
│   └── AIDesignTestForm.json     ← 欄位清單（1_xml_tool 反解產生，供對照）
└── 流程/
    ├── AI設計的流程測試.bpmn      ← 匯入流程設計器
    └── AI設計的流程測試.json      ← 關卡與權限清單（反解產生，供對照）
```

---

## 1. 匯入順序

**一定要先表單、後流程** —— 流程的欄位權限字串引用表單欄位 ID，表單不在會對不上。

1. 匯入 `AIDesignTestForm.form`
   - 表單 ID：`AIDesignTestForm`
   - 表單名稱：`AI設計的流程測試`
   - 若設計器在匯入時要求另外指定表單 ID，**務必填 `AIDesignTestForm`**；
     填別的會讓流程的欄位權限全部失效（權限字串的第一層標籤就是表單 ID）。
2. 匯入 `AI設計的流程測試.bpmn`
   - 流程包 ID：`AIDesignTestProcess`
   - 流程名稱：`AI設計的流程測試`
3. 發佈流程，再從待辦開一張單。

**只匯入 191 測試區**（`10.10.130.191:8080`）。190 正式區不要碰。

---

## 2. 流程長相

```
起點 ──▶ 開單人 ──▶ 直屬主管 ──▶ 結案
       (ApplyUserTask)  (ManagerUserTask)
       PROCESS_REQUESTER    MANAGER
```

| 關卡 | ID | 執行者 | 可編輯欄位 |
|:---|:---|:---|:---|
| 開單人 | `ApplyUserTask` | 流程申請人 | 28 項（幾乎全部） |
| 直屬主管 | `ManagerUserTask` | 申請人的直屬主管 | 4 項：備註、急件等級、手寫簽名、附件 |

**主管關卡刻意只開 4 個欄位**，其餘唯讀 —— 這是驗證「同一張表單在不同關卡呈現不同樣貌」是否生效的觀察點。
鼎新只存 `ENABLED` / `INVISIBLE` / `FULL_CONTROL` 三種值，**唯讀的作法是不列出**，不是寫某個值。

---

## 3. 表單上要測的功能

| 功能 | 元件 ID | 型別 | 怎麼測 |
|:---|:---|:---|:---|
| **按鈕帶入部門與人員** | `PickUserButton` | 按鈕 | 按下去應自動填入下面兩個雙欄位 |
| 　└ 人員（工號／姓名） | `EmpDialogInputLabel` | 按鈕+雙輸入框 | 兩格分別是工號與姓名 |
| 　└ 部門（代號／名稱） | `DeptDoubleTextBox` | 雙輸入框 | 兩格分別是部門代號與名稱 |
| **檔案上傳** | `UploadFileButton` + `Attachment` | 按鈕 + 附件區 | 按鈕把畫面捲到附件區，用 BPM 內建附件上傳 |
| **明細表格** | `ItemGrid` | 表格 | 欄位：項次／品名／數量。先填上方三個輸入框，再按表格的「新增」 |
| 　└ 表格繫結欄位 | `ItemNoTextBox` / `ItemNameTextBox` / `ItemQtyTextBox` | 輸入框 | 表格三欄各繫結一個 |
| 一般輸入 | `SubjectTextBox`、`ContentTextArea` | 輸入框／輸入區域 | 主旨與內容說明，皆為必填 |
| 日期時間 | `NeedDate`、`NeedTime` | 日期／時間 | 需求日期為必填 |
| 選項 | `UrgencyRadio`、`NotifyCheckBox`、`CategoryDropDown`、`SiteListBox` | 單選／複選／下拉／列表 | 申請類別選「其他」時，相關單號欄位才會出現 |
| 其他按鈕型元件 | `RelatedNoDialogInput`、`RemarkDialogInputMulti` | 按鈕+輸入框／按鈕+輸入區域 | |
| 單號 | `SerialNumber` | 單號 | 需要 BPM 端設好單號規則才會有值 |
| 其他 | `PasswordTextBox`、`LogoImage`、`RefLink`、`FormBarcode`、`FormQRCode`、`SignHandWriting`、`SubTab22` | | 密碼／圖片／連結／條碼／QR／手寫／分頁 |

必填檢核寫在 `formSave()`：主旨、內容說明、申請人、需求日期任一為空會擋下送出（只在開單關卡檢查）。

---

## 4. 已知風險與觀察點

這份檔案通過了靜態檢查與反解對比（`python 8_BPMAIworker/tools/verify.py`），
但**尚未實際匯入過鼎新設計師**。以下幾點是最可能出問題的地方，匯入時請優先確認：

| 風險 | 徵狀 | 若發生 |
|:---|:---|:---|
| **OID 自編** | 匯入報錯或蓋掉別的定義 | 本檔的 44 個 OID 全部換成新的一組（前綴 `7a10d0xx`）。若鼎新是沿用檔案內的 OID 而非重配，請回報實際行為，這是 `8_BPMAIworker/PLAN.md` 第 7 節第 1 點的未知數 |
| **新增元件後重編 XStream id** | 表單開不起來、元件遺失 | 表單的 747 個節點已重編為 880 個並保持連號 |
| **表格欄位定義** | 表格沒有欄位、或新增列沒反應 | 三欄的結構抄自線上表單 `SolarEnergyECRECN` 的表格欄位；若行為不對，先確認欄位有沒有正確繫結 |
| **`ajax_OrgAccessor.findCurrentUser` 的回傳欄位名** | 按「帶入部門與人員」時工號姓名有進去、部門是空的並跳提示 | 打開 F12 主控台看印出來的回傳物件，把 `AIDesignTestForm.js` 的 `fillApplicant()` 裡的欄位名改對，再重跑 `python 8_BPMAIworker/tools/build_form.py` |
| **`FormUtil.setValue` 對雙欄位的寫法** | 雙欄位只填到第一格 | 目前用 `FormUtil.setValue(id, [第一格, 第二格])`。若不成立，需改成分別對兩個子欄位設值 |
| **表單 ID 被匯入畫面改掉** | 各關卡欄位權限全部失效 | 匯入時表單 ID 必須是 `AIDesignTestForm` |

---

## 5. 重新產生

改了設定或腳本之後：

```bash
python 8_BPMAIworker/tools/build_form.py
```

```bash
python 8_BPMAIworker/tools/build_bpmn.py
```

```bash
python 8_BPMAIworker/tools/verify.py
```

`build_form.py` 會把同目錄的 `AIDesignTestForm.js` 重新內嵌進 `.form`，
所以腳本要改就改 `.js`，不要直接改 `.form` 裡的逃脫字串。
