# BPM 表單設計器 — 腳本可用資源清冊

> 建立日期：2026-09-07
> 適用：表單設計師 → 腳本編輯器（`RwdFormScriptEditor`）
> 來源：`NaNaWeb.war`（1,390 個 JS 檔）、`WEB-INF/dwr-default.xml`、`WEB-INF/classes`
> 姊妹文件：[BPM系統地圖.md](BPM系統地圖.md)、[BPM_ERP整合介面.md](BPM_ERP整合介面.md)

---

## 一、先講結論

你目前用的三支：

```javascript
document.write('<script src="../../CustomJsLib/EFGPShareMethod.js"></script>');           // 21 個函式
document.write('<script src="../../dwrDefault/interface/ajax_DatabaseAccessor.js"></script>'); // 35 個方法
document.write('<script src="../../js/CustomDataChooser.js"></script>');                  // 資料選擇器
```

可用但你還沒用到的：

| 類別 | 數量 | 說明 |
|---|---|---|
| **DWR 後端服務** | **45 支 / 866 個方法** | 你只用了 1 支（`ajax_DatabaseAccessor`） |
| CustomJsLib 共用函式庫 | 20 支 | |
| js/ 前端函式庫 | 1,390 個檔 / 41 個子目錄 | |
| **表單頁面預設已載入** | 28 支 | **不用 `document.write`，直接呼叫即可** |

---

## 二、表單頁面預設已載入（直接用，不需 document.write）

這是最容易被忽略的部分。`app/RwdFormPreviewer.jsp` 已經幫你載好：

| 類別 | 檔案 | 你可以直接用 |
|---|---|---|
| **DWR 引擎** | `dwrDefault/engine.js`、`dwrDefault/util.js` | ✅ 所以你只需要載 `interface/ajax_XXX.js` |
| jQuery | `jquery-a.k.c.min.js`（3.x）、`jquery-ui-a.j.c.custom.js` | `$()` 全套 |
| Bootstrap | `bootstrap-c.c.e.min.js` | Modal、Tooltip 等 |
| **表格** | `bootstrap-table-1.18.3_BPMcustomized.js`、`BpmTable.js` | 排序、分頁、固定欄 |
| 日期 | `BpmCalendar.js` | 日曆元件 |
| **驗證** | `formValidation.js` | 表單驗證 |
| **表單工具** | `FormUtil.js` | `SectionToChinese()`、Tab 控制 |
| **對話框** | `ModalDialog.js`、`Dialog.js` | 彈出視窗 |
| **開窗** | `OpenWin.js` | 4 個 DataChooser 函式（見下） |
| 核心 | `ds.js`（908 行） | 系統共用 |
| MVVM | `knockout-3.2.0.js`、`knockout.mapping.js` | 資料繫結 |
| UI | `materialize.min.js` | Material Design |
| **QR Code** | `jquery.qrcode.min.js`、`BpmAppQRCode.js` | 產生 QR Code |
| **手寫簽名** | `jSignature.js`、`BpmAppHandWriting.js` | 簽名板 |

### OpenWin.js 的 4 個開窗函式（已預載）

```javascript
openDataChooser(pServiceName, pWindowType, pOtherArguments, pOpenerObjectName, pOpenerMethodName, pViewType)
openUserDataChooser(pServiceName, pWindowType, pOtherArguments, pOpenerObjectName, pOpenerMethodName, pIsContainLeaveUser)
openDataChooserWithSelectAll(pServiceName, pWindowType, pOtherArguments, pOpenerObjectName, pOpenerMethodName, pSelectAll)
openDataChooserWithSelectedOptions(pServiceName, pWindowType, pOtherArguments, pOpenerObjectName, pOpenerMethodName, pHdnInitDataId, pViewType)
```

> 這幾支是**選人/選組織**用的，跟 `EFGPShareMethod.js` 的 `singleOpenWin`（選資料庫資料）不同用途。

---

## 三、DWR 後端服務 — 45 支 / 866 個方法

### 用法

```javascript
document.write('<script src="../../dwrDefault/interface/ajax_XXX.js"></script>');
// 然後
ajax_XXX.方法名(參數1, 參數2, function(result){ /* callback */ });
```

> **注意**：`dwrDefault/interface/` 目錄裡沒有實體檔案——這些 JS 是 DWR 在執行期依 `dwr-default.xml` **動態產生**的。所以你在檔案總管裡找不到，但 URL 可以正常載入。

### 完整清單（依方法數排序）

| JS 名稱 | 方法數 | 用途 |
|---|---|---|
| `ajax_IsoModuleAccessor` | 112 | ISO 文管 |
| `ajax_WmsAccessor` | **110** | **流程管理主服務（最大宗）** |
| `formDesignerAjax` | 62 | 表單設計器 |
| `ajax_ProcessAccessor` | **43** | **流程操作（加簽、會辦、關卡）** |
| `ajax_BpmMobileWorkItemAccessor` | 39 | 行動版待辦 |
| **`ajax_DatabaseAccessor`** | **35** | **資料庫存取（你在用的）** |
| `ajax_MobileDatabaseAccessor` | 32 | 行動版資料庫 |
| `ajax_MobileManageAccessor` | 31 | 行動版管理 |
| `ajax_BpmMobileAccessor` | 31 | 行動版主服務 |
| **`ajax_FormAccessor`** | **26** | **表單資料存取** |
| `ajax_ExtOrgAccessor` | 25 | 擴充組織 |
| `ajax_SapAccessor` | 24 | SAP 整合 |
| `ajax_SystemScheduleAccessor` | 20 | 系統排程 |
| `ajax_BAMAccessor` | 20 | 商業活動監控 |
| `ajax_CriticalAccessor` | 19 | Critical 模組 |
| **`ajax_OrgAccessor`** | **18** | **組織／人員查詢** |
| `ajax_MobileWeChatAccessor` | 18 | 微信 |
| `ajax_LanguageAccessor` | 18 | 多語系 |
| `ajax_AnnouncementManageAccessor` | 18 | 公告 |
| `ajax_CommonAccessor` | 16 | 共用（session、登入資訊） |
| `ajax_BpmMobileTracessAccessor` | 13 | 行動版追蹤 |
| `ajax_AppFormAccessor` | 11 | AppForm |
| `ajax_IsoAttTemplatesAccessor` | 10 | ISO 附件範本 |
| `ajax_AdapterAccessor` | 10 | 轉接器 |
| `ajax_MCloudAccessor` | 9 | MCloud |
| `ajax_ServiceRegisterAccessor` | 8 | 服務註冊 |
| `ajax_AdapterManageAccessor` | 8 | 轉接器管理 |
| `ajax_ReportModuleAccessor` | 7 | 報表 |
| `IsoAuthorityGroupAccessor` | 7 | ISO 權限群組 |
| `ajax_OnlineReadAccessor` | 6 | 線上閱讀 |
| **`ajax_CustomModuleAccessor`** | **6** | **客製模組（官方客製管道）** |
| `ajax_AdapterDingtalkTodoTaskAccessor` | 6 | 釘釘待辦 |
| `ajax_TiptopAccessor` | 5 | **TIPTOP ERP** |
| `ajax_ResignationAccessor` | 5 | 離職 |
| `ajax_MobileUserAccessor` | 5 | 行動版使用者 |
| `ajax_MobileSubscribeAccessor` | 5 | 行動版訂閱 |
| `ajax_MobileScheduleAccessor` | 5 | 行動版排程 |
| `WebUtil` | 5 | 工具 |
| `ajax_IntelligentLearningAccessor` | 3 | 智慧學習 |
| `ajax_EBGAccessor` | 3 | EBG |
| `ajax_BpmMobileContactUserAccessor` | 3 | 行動版通訊錄 |
| `WebServiceUtil` | 3 | Web Service 橋接 |
| `treeViewDataChooserAjax` | 2 | 樹狀選擇器 |
| `ajax_MobileFileAccessor` | 2 | 行動版檔案 |
| `WorkFlowWebServiceUtil` | 2 | 流程 Web Service |

---

## 四、重點服務的方法明細

### 4.1 ajax_DatabaseAccessor（你在用的，35 個）

**查詢**

```javascript
executeQuery(資料庫設定ID, SQL, 參數List, 型別int[])          // 一般查詢
executeQueryByPage(資料庫設定ID, SQL, 參數List, 型別[], 起, 迄)  // 分頁查詢
executeNonArgQuery(資料庫設定ID, SQL)                        // 無參數查詢
executeQueryByDs(資料庫設定ID, SQL, 參數List, 型別[])          // 指定 DataSource
executeQueryIncludeComma(...)                              // 含逗號資料
query(SQL, 參數List, 型別[])                                 // 簡化版
queryWithCondition(SQL, 參數List, 型別[], 條件, 條件)
queryToJson(SQL, 參數List, 型別[], 欄位String[])              // 直接回 JSON
```

**寫入**

```javascript
executeUpdate(資料庫設定ID, SQL, 參數List, 型別int[])
executeNonArgUpdate(資料庫設定ID, SQL)
executeUpdateByDs(資料庫設定ID, SQL, 參數List, 型別[])
update(SQL, 參數List, 型別[])
updateWithCondition(SQL, 參數List, 型別[], 條件)
```

**圖表資料**

```javascript
getChartData(資料庫設定ID, SQL, 參數List, 型別[])
queryForChartData(...)
executeQueryForChartTemplate(...)
```

**選擇器專用**

```javascript
queryForCustomDataChooser(SQL, 參數List, 型別[], List, List)  // CustomDataChooser.js 用這支
queryForProductDataChooser(...)
queryForDataChooserConf(...)
queryBySqlForDataChooser(...)
```

**其他**：`getDBType()`、`findAllSqlTypes()`、`findAllLocaleTypes()`、`convertSql()`

### 4.2 ajax_OrgAccessor（組織查詢，18 個）

```
findCurrentUser        findUserById       findUserByOID      findUserByOrgEmpId
findUserNames          findOrgById        findOrgByOID       findOrgUnitById
findOrgUnitByOID       findGroupById      findGroupByOID     getAllOrg
getDepartments         getGroups          getProjects
countWorkingTime       fetchWorkDate      ← 工時／工作日計算
```

> `findCurrentUser()` 常用來取當前登入者；`countWorkingTime` / `fetchWorkDate` 可算工作天。

### 4.3 ajax_FormAccessor（表單資料，26 個）

```
findFormInstance              findFormDefinition           findFormDefinitionById
findFieldValue                findSerialNumber             findAttachment
findFormOIDsOfProcess         findFormDefinitionGridInfo   findFormInstanceGridInfo
getFormFieldDataByFormDefOID  getFormInstanceAttachmentSize
ReadExcel                     ReadExceltoStringFormat      ← 讀 Excel
performQuery  performUpdate  performNonArgQuery  performNonArgUpdate
searchExportedFormData        fetchAttachmentDataToFormInstace
```

### 4.4 ajax_ProcessAccessor（流程操作，43 個）

**查詢類**
```
findProcessInstance      findProcessPackage       findActDataForProcessId
findActLocationForProcessId    findExecutiveComment     findExecutiveCommentBySN
findNotEmptyComment      getProcessInstByAJAX     getWorkFlowTree
```

**動態加關卡類**（加簽／會辦程式化控制）
```
addCustomParallelActivity        addPreCustomActivity       addPostCustomActivity
addInvokeCustomActivity          addBlockActPosteriorAct    addDecisionRuleListAct
（每支都有 ...Always 版本）
```

**其他**：`accepWorkItem`、`assignRelevantData`、`upgradeReadOnlyFormStatus`、`markingProcessUserFocus`

### 4.5 ajax_CommonAccessor（共用，16 個）

```
findCurrentUser 相關：getSessionValue  removeAttributeFormSession  setKey
連線資訊：getConnectedUserInfoCount  updateConnectedUserInfo  checkUserIP
其他：getServerUrl  getCountdown  getCountdownTime  login  toStringData
```

---

## 五、CustomJsLib 共用函式庫

| 檔案 | 大小 | 內容 |
|---|---|---|
| **`EFGPShareMethod.js`** | 20 KB | **21 個函式（你在用的，見下）** |
| `EFGPShareMethodCate.js` | 4 KB | 分類版 |
| **`EFGP_GIGA.js`** | 3 KB | **貴公司自己的**：`ChangLOGO`、`GetDS`、`Test` |
| `MobileCustomOpenWin.js` | 24 KB | 行動版開窗 |
| `Publisher.js` | 10 KB | 發佈相關 |
| `CustISONew.js` | 16 KB | ISO 客製 |
| `wangEditor.min.js` | 262 KB | 富文本編輯器 |
| `log4js.js` | 50 KB | 前端 log |
| `getActualLength.js` | 2 KB | 中文字長度計算 |
| `attendance.js`、`tiptopmemo.js`、`sselect.js`、`initial.js`、`StanDisp.js`、`wards_j.js` | 小 | 各式小工具 |

另有子目錄：`backup/`、`new/`、`stan/`、`prefixAction/`、`prefixDocument/`

### EFGPShareMethod.js 的 21 個函式

**開窗（選資料庫資料）**
```javascript
singleOpenWin(檔名, 資料庫設定ID, SQL, SQL標題, QBE欄位, QBE標題, 回填欄位ID, 寬, 高, 全取, 額外條件)
singleOpenWinHidden(檔名, 資料庫設定ID, SQL, SQL標題, QBE欄位, QBE標題, 隱藏欄, 回填欄位ID, 寬, 高)
pluralityOpenWin(檔名, 資料庫設定ID, SQL, SQL標題, QBE欄位, QBE標題, 原始資料, 寬, 高, 全取)  // 多筆
```

**SQL 下拉選單**
```javascript
getDropDownFromSQL(資料庫設定ID, 元件ID, 隱藏欄ID, SQL)
getDropDownFromSQLForTxt(資料庫設定ID, 元件ID, 隱藏欄ID, 文字欄ID, SQL)
setDropDownFromSQL(data)          // callback
setDropDownFromSQLForTxt(data)    // callback
```

**欄位顯示控制**
```javascript
showColumn(pId)          hideColumn(pId)
hideFrame(pId)           changeFrameUnderTheBorder(pId)
componentDisable(pId, 狀態)       componentBgColor(pId, 顏色)
clearColumnValue(pId)
```

**數值處理**
```javascript
numberCheck(pId, 狀態)
floatNumbersCheck(pId, 小數位, 訊息)
roundMath(值, 位數)
setThousandths(值, 是否加千分位)
```

**工具**：`trim()`、`ParseXml()`、`objectEval()`

---

## 六、js/ 目錄可用資源（92 支根目錄 + 41 個子目錄）

### 常用（根目錄）

| 檔案 | 用途 |
|---|---|
| **`common_util.js`** | **26 個驗證函式**（見下） |
| `CustomDataChooser.js` | 自訂資料選擇器（你在用的） |
| `StringUtil.js` | `htmlencode`、`htmldecode` |
| `formValidation.js` | 表單驗證 |
| `snGenRule.js` | 單號產生規則 |
| `BpmTable.js`、`SubGridTransfer.js` | 表格／子表格 |
| `bpm-qrcode.js`、`bpm-handWriting.js` | QR Code、手寫 |
| `E10Form.js` | E10 ERP 表單 |
| `Map.js`、`Order.js` | 資料結構 |
| `aes.js` | AES 加解密 |
| **`echarts.min.js`、`morris.js`、`raphael.js`** | **圖表繪製** |
| `jquery.qrcode.min.js`、`jSignature.js` | QR、簽名 |

### common_util.js 的驗證函式（26 個）

```javascript
validateLength(欄位ID, 長度, 訊息)          validateEmpty(欄位ID, 訊息)
validateInputByArray(欄位ID, 陣列, 訊息)    validateInputByRange(欄位ID, 最小, 最大, 訊息)
compareDate(日期1, 日期2, 訊息)             IsDate(欄位)      IsDateTime(欄位)
dateDiff(間隔, 起, 迄)                     formatdate(日期)   formatCurrency(數字)
checkInt / checkIntBetween / checkEqualIntBetween / checkfloat / checkString
trim / ltrim / rtrim
SQLTypes()  DateTimePatterns()  OrgUnitTypes()  NaNaDataSource()   ← 常數表
```

### 值得注意的子目錄

| 目錄 | 內容 |
|---|---|
| `js/formDesigner/` | 設計器本身的實作（16 支，約 1 MB） |
| `js/Mobile/`、`js/BPMMobile/` | 行動版 |
| `js/NewTiptop/`、`js/ajaxSap/` | **ERP 整合前端** |
| `js/MVVM/` | Knockout |
| `js/SheetJS-0.14.3/` | **Excel 讀寫** |
| `js/pdfJs/`、`js/PDFWebView/` | PDF 呈現 |
| `js/bpmn-js/` | BPMN 流程圖 |
| `js/zTreeJs/` | 樹狀元件 |
| `js/jqueryfileupload/`、`js/uploadify/` | 檔案上傳 |
| `js/CodeMirror-master/`、`js/SyntaxHighlighter/` | 程式碼編輯／highlight |
| `js/spectrum/`、`js/colorpicker-master/` | 顏色選擇 |
| `js/clipboard/` | 剪貼簿 |
| `js/customModule/`、`js/CustomJsLib/` | 客製 |

---

## 七、實用建議

### 7.1 路徑寫法

腳本執行時的相對位置是 `/NaNaWeb/某模組/某頁面`，所以：

```javascript
'../../CustomJsLib/xxx.js'          → /NaNaWeb/CustomJsLib/xxx.js
'../../js/xxx.js'                   → /NaNaWeb/js/xxx.js
'../../dwrDefault/interface/xxx.js' → /NaNaWeb/dwrDefault/interface/xxx.js
```

### 7.2 不要重複載入已預載的

`jQuery`、`DWR engine/util`、`FormUtil`、`OpenWin`、`ModalDialog`、`Dialog`、`ds.js`、
`formValidation`、`BpmTable`、`BpmCalendar` **都已經載好了**，再 `document.write` 一次可能造成版本衝突。

（你截圖中的 `jQuery-1.7.2.js` 在 CustomJsLib 裡是舊版，而表單頁預載的是 jQuery 3.x——混用會出問題。）

### 7.3 外部 CDN 的風險

你腳本裡有幾支指向 `http://10.10.130.122:5148/modules/...`（popper、tippy、quill、axios）。
這是內網某台主機，**不是 BPM 主機**（BPM 是 `10.10.130.191:8080`）。那台若停機或改 IP，所有引用它的表單都會壞。
建議把這些第三方套件放進 `NaNaWeb/CustomJsLib/` 或 `js/`，跟 BPM 一起走版控。

### 7.4 客製的正式管道

`ajax_CustomModuleAccessor`（6 個方法）是官方留給客製用的：

```javascript
accessModule(參數)        getModuleWebSite(參數)     getISOModuleSite()
setCreateFormData(資料)   getCreateFormData(布林)
```

---

## 八、安全注意事項

### 8.1 DWR 沒有方法白名單

`dwr-default.xml` 的 45 個 `<create>` 中，**`<include method="...">` 數量為 0**——
代表每個服務類別的**所有 public 方法**都對前端開放，合計 **866 個方法**。

其中 `ajax_DatabaseAccessor` 開放了 `executeUpdate`、`executeNonArgUpdate`——
**瀏覽器端可以直接送出 SQL 寫入指令**。

### 8.2 DWR 端點不經過統一安全過濾

`NaNaWeb.properties`：

```
jspFilter.ignore.urlToken.5=/dwr
```

DWR 路徑被排除在 JSP filter 之外，授權檢查由各 Accessor 類別自行負責。

> 這兩點是原廠設計，不是你們改出來的。但如果 BPM 有對外開放（非純內網），值得請鼎新確認 `DatabaseAccessor` 的權限控管方式。
