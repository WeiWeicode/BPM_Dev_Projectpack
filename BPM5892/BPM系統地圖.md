# 鼎新 BPM 系統地圖

> 建立日期：2026-09-07
> 來源：`standalone\deployments\NaNaWeb.war\WEB-INF\`
> 依據：`web.xml`（68 個 Struts 模組註冊）、49+18 個 `struts-*-config.xml`、`dwr-default.xml`
> 姊妹文件：[BPM系統分析.md](BPM系統分析.md)

---

## 一、系統入口總覽

`web.xml` 定義的所有 servlet 進入點：

| URL 樣式 | Servlet | 用途 |
|---|---|---|
| **`/GP/*`** | **ActionServlet** | **Struts 主入口——254 條路由全在這** |
| `/dwrDefault/*` | dwr-default-invoker | **DWR：前端 JS 直呼後端（45 個服務）** |
| `/webservice/servlet/AxisServlet`、`/services/*`、`*.jws` | AxisServlet | SOAP Web Service |
| `/DownloadFile/*` | FileDownloader | 附件下載 |
| `/DownloadISOFile/*` | ISOFileDownloader | ISO 文件下載 |
| `/MobileDownloadFile/*` | MobileFileDownloader | 行動版下載 |
| `/MultiFormDocUploader` | MultiFormDocUploader | 表單附件上傳 |
| `/dataservlet` | DataServlet | 資料存取 |
| `/notifier` | NotifierServlet | 推播通知 |
| `/Barbecue/barcode` | BarcodeServlet | 條碼產生 |
| `/app/PreDelegate` | PreDelegateServlet | 代理人前置處理 |
| `*.DocumentsList`、`*.FileQuery`、`*.EffectInvalid` | CreateISO*ExcelServlet | ISO 清單匯出 Excel |
| `/webservice/SOAPMonitor`、`/webservice/servlet/AdminServlet` | SOAP 管理 | 開發/管理用 |

### URL 組成規則

```
http://<host>/NaNaWeb/GP/<模組路徑>/<action路徑>?hdnMethod=<方法名>
                      └─ ActionServlet    └─ struts-config 的 path
例：
/NaNaWeb/GP/WMS/PerformWorkItem/PerformWorkItemMain?hdnMethod=mailStraightSignOff
/NaNaWeb/GP/Authentication?hdnMethod=login
```

**關鍵**：Struts action 走 `parameter="hdnMethod"` 的 DispatchAction 模式——同一個 action 類別底下用 `hdnMethod` 參數再分派到不同方法。所以 **254 條路由只是骨架，實際功能點數量是它的好幾倍**。

---

## 二、功能模組地圖（68 模組 / 254 路由）

### 2.1 流程執行核心

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/PerformWorkItem` | **26** | PerformWorkItemAction、PerformRequesterActivityAction、FormHandler |
| `/WMS/ValidateProcess` | 4 | ValidateProcessAction、**Bpm**ValidateProcessAction |
| `/WMS/CreateProcessDocument` | 2 | CreateProcessDocumentAction、**Bpm**CreateProcessDocumentAction |
| `/WMS/ManageDraft` | 2 | ManageDraftAction、**Bpm**ManageDraftAction |
| `/WMS/DealDoneWorkItem` | 2 | DealDoneWorkItemAction、**Bpm**DealDoneWorkItemAction |
| `/WMS/AbortProcess` | 2 | AbortProcessAction、**Bpm**AbortProcessAction |
| `/WMS/RedoInvoke` | 2 | RedoInvokeAction、**Bpm**RedoInvokeAction |
| `/WMS/Restful` | 1 | RestfulWorkProcessAction |

> `PerformWorkItem`（26 條）是**整個系統最核心的模組**——待辦簽核、加簽、退回、會辦都在這裡。

### 2.2 流程追蹤與監控

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/TraceProcess` | **26** | TraceProcessAction、ProcessTracer、**Bpm**ProcessTracer、RelevantDataViewer |
| `/WMS/TraceRelationalProcess` | **19** | TraceRelationalProcessAction、RelationalProcessTracer |
| `/WMS/GatherWfStatistics` | 15 | GatherWfStatisticsAction |
| `/WMS/PreviewProcess` | 10 | ProcessPreviewer、**Bpm**ProcessPreviewer、ViewProcessPackage |
| `/WMS/BusinessProcessMonitor` | 2 | BusinessProcessMonitorAction |
| `/WMS/ProcessPerformanceMonitor` | 1 | ProcessPerformanceMonitorAction |

### 2.3 設計工具

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/FormDesigner` | 9 | FormDesignerAction |
| `/WMS/ProcessModule` | 3 | ProcessModuleAction |
| `/WMS/ManageModule` | 3 | ManageModuleAction |
| `/WMS/DesignerDownload` | 1 | DesignerDownloadAction |
| `/(root)` `/ToolSuite` | — | ToolSuiteAction（設計師啟動入口，含 T100 整合參數） |

### 2.4 ISO 文件管理

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/ManageDocument` | 8 | ManageDocumentAction、CreateDocumentAction、DocFileUploader、BatchUploader |
| `/WMS/ManageAttachmentTemplates` | 4 | ManageAttTemplatesAction |
| `/WMS/ImportEasyFlowISO` | 2 | ImportEasyFlowISOAction |
| `/WMS/ManageDocType` / `ManageDocFile` / `ManageDocDraft` / `ManageDocClause` / `ManageDocCategory` | 各 1 | 對應的 Manage*Action |
| `/WMS/ManageISOAuthority` / `ManageISOWatermarkPattern` / `ManageAccessRight` | 各 1 | 權限與浮水印 |
| `/WMS/OnlineRead` | 1 | FormDocUploader（線上閱讀） |

### 2.5 組織與使用者

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/ManageUserProfile` | 11 | ManageUserProfileAction |
| `/WMS/ResignedEmployeesMaintain` | 4 | ResignedEmployeesMaintainAction（離職人員待辦移轉） |
| `/WMS/SearchOrgData` | 3 | SearchOrgDataAction |
| `/WMS/OnlineUser` | 2 | OnlineUserAction |
| `/WMS/ManageUserCurrentType` | 1 | UserManageAction |
| `/WMS/ManageSecurityLevel` | 1 | ManageSecurityLevelAction |

### 2.6 資料查詢與報表

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/SearchFormData` | 6 | SearchFormDataAction、**Bpm**SearchFormDataAction |
| `/WMS/CustomQuery` | 5 | CustomQueryMaintenAction |
| `/WMS/ManageCustomReport` | 3 | ManageCustomReportAction、FormDocUploader、StrutsFileDownloader |
| `/WMS/ColumnMask` | 2 | ColumnMaskAction（欄位遮罩） |
| `/WMS/FormDataMainten` | 1 | FormDataMaintenAction |
| `/WMS/ManageReport` | 1 | ManageReportAction |

### 2.7 外部系統整合

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/IntegratePortalURLEntrance` | 2 | IntegratePortalURLEntranceAction、**Bpm**版 |
| `/WMS/Mcloud` | 2 | McloudAction |
| `/WMS/Sap` | 1 | SapAction |
| `/WMS/Sysintegration` | 1 | SysintegrationSetAction |
| `/WMS/ManageSysIntegration` | 1 | SysIntegreationAction |
| `/WMS/AppFormModule` | 1 | AppFormModuleAction |

### 2.8 系統管理

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/ManageSystemConfig` | 5 | ManageSystemConfigAction |
| `/WMS/LanguageMaintain` | 4 | LanguageMaintainAction |
| `/WMS/ManagePhrase` | 2 | ManagePhraseAction（常用詞句） |
| `/WMS/FavoritiesMaintain` | 2 | FavoritiesMaintainAction |
| `/WMS/License` | 2 | LicenseModuleAction |
| `/WMS/SystemSchedule` | 1 | SystemScheduleAction |
| `/WMS/ServiceRegister` | 1 | ServiceRegisterAction |
| `/WMS/ManageWfNotification` | 1 | ManageWfNotificationAction |
| `/WMS/ManageNotificationContent` | 1 | ManageNotificationContentAction |
| `/WMS/ManageSnGenRule` | 1 | ManageSnGenRuleAction（單號產生規則） |
| `/WMS/ManageCuzPattern` | 1 | ManageCuzPatternAction |
| `/WMS/UpdateVersion` | 1 | UpdateVersionAction |
| `/WMS/InstallCertificate` | 1 | InstallCertificateAction |
| `/WMS/IgnoreFilter` | 1 | IgnoreFilterAction |
| `/WMS/AdministratorFunction` | 1 | AdministratorFunctionAction |

### 2.9 行動版與其他

| 模組 | 路由 | 後端 Action |
|---|---|---|
| `/WMS/Mobile` | 6 | MobileWorkProcessAction、MobilePortletsAction、MobileWorkProcessDemoAction |
| `/OpenWin` | 6 | DataChooser、TreeViewDataChooser、OpenWinForNCHCAction |
| `/(root)` | 16 | SecurityLoginAction、ForwardIndexAction、ToolSuiteAction |

---

## 三、根模組（登入與驗證）

`struts-common-config.xml`——所有身分驗證都經過 **`SecurityLoginAction`** 這一支：

| URL | 用途 |
|---|---|
| `/GP/Authentication` | 主登入 |
| `/GP/Logout` | 登出 |
| `/GP/ExtraLogin` | 從郵件連結等外部入口的補登入 |
| `/GP/PerformWorkFromMail` | 郵件直接簽核 |
| `/GP/BpmPerformWorkFromMail` | 同上（BPM 版，保留相容） |
| `/GP/VerifyPasswordMain` | 密碼二次確認（簽核用） |
| `/GP/VerifyPasswordForByPass` | 略過關卡的密碼確認 |
| `/GP/LoginServer2` | 多主機在地化的第二台登入 |
| `/GP/ForwardIndex` | 登入後導向首頁（ForwardIndexAction） |
| `/GP/ToolSuite` | 設計師工具啟動（ToolSuiteAction） |
| `/GP/ProductManifest` | 產品資訊 |

### 登入表單欄位（`frmSecurityLogin`）

除了帳密（`txtUserId` / `txtPsd`），還帶了大量整合用參數，可看出支援的情境：

| 欄位 | 情境 |
|---|---|
| `ticket` | CAS 單一登入 |
| `hdnSSOKey` | **T100 ERP 整合驗證** |
| `oauthUid` | OAuth |
| `hdnQRcodeToken` | QR Code 登入 |
| `hdnPushToken` | 行動推播 |
| `hdnLdapId` | LDAP |
| `hdnMailStraightSignOff` | 郵件一鍵簽核 |
| `hdnLogoutForMultiLogin` | 多重登入處理 |
| `ddid` | 釘釘（DingTalk） |

### 全域例外處理

三層都導向 `com.dsc.nana.user_interface.web.util.ExceptionCatcher`：
`BusinessDelegateException` → `ServletException` → `java.lang.Exception`

---

## 四、DWR 服務地圖（45 個，前端 JS 可直呼）

前端寫 `ajax_XxxAccessor.方法名(參數, callback)` 就會呼到後端。全部位於
`com.dsc.nana.user_interface.web.ajax_service.helper.*`

### 核心

| JS 名稱 | 後端類別 | 用途 |
|---|---|---|
| `ajax_CommonAccessor` | CommonAccessor | 共用 |
| `ajax_WmsAccessor` | WmsAccessor | 流程管理主服務 |
| `ajax_ProcessAccessor` | ProcessAccessor | 流程 |
| `ajax_FormAccessor` | FormAccessor | 表單 |
| `ajax_DatabaseAccessor` | DatabaseAccessor | **直接資料庫存取** |
| `ajax_OrgAccessor` / `ajax_ExtOrgAccessor` | OrgAccessor | 組織架構 |
| `WebUtil` | WebUtil | 工具 |

### 模組專用

| JS 名稱 | 用途 |
|---|---|
| `ajax_IsoModuleAccessor`、`IsoAuthorityGroupAccessor`、`ajax_IsoAttTemplatesAccessor` | ISO 文管 |
| `formDesignerAjax`、`treeViewDataChooserAjax` | 設計工具 |
| `ajax_CustomModuleAccessor` | **客製模組（貴公司的客製 JS 呼這支）** |
| `ajax_CriticalAccessor`、`ajax_EBGAccessor` | Critical / EBG 模組 |
| `ajax_ReportModuleAccessor`、`ajax_OnlineReadAccessor` | 報表 / 線上閱讀 |
| `ajax_LanguageAccessor`、`ajax_SystemScheduleAccessor` | 多語系 / 排程 |
| `ajax_AnnouncementManageAccessor`、`ajax_ResignationAccessor` | 公告 / 離職 |
| `ajax_ServiceRegisterAccessor`、`ajax_BAMAccessor` | 服務註冊 / BAM |

### 行動版（9 支）

`ajax_BpmMobileAccessor`、`ajax_BpmMobileWorkItemAccessor`、`ajax_BpmMobileTracessAccessor`、
`ajax_BpmMobileContactUserAccessor`、`ajax_MobileFileAccessor`、`ajax_MobileManageAccessor`、
`ajax_MobileScheduleAccessor`、`ajax_MobileDatabaseAccessor`、`ajax_MobileSubscribeAccessor`、
`ajax_MobileUserAccessor`

### 外部整合

| JS 名稱 | 對象 |
|---|---|
| `ajax_TiptopAccessor` | **鼎新 TIPTOP ERP** |
| `ajax_SapAccessor` | SAP |
| `ajax_MCloudAccessor` | 鼎新 MCloud |
| `ajax_MobileWeChatAccessor` | 微信 |
| `ajax_AdapterDingtalkTodoTaskAccessor` | 釘釘待辦 |
| `ajax_AdapterAccessor`、`ajax_AdapterManageAccessor` | 通用轉接器 |
| `ajax_IntelligentLearningAccessor` | 智慧學習 |
| `WebServiceUtil`、`WorkFlowWebServiceUtil` | SOAP Web Service 橋接 |

---

## 五、架構觀察

### 5.1 雙軌 Action：EFGP 原版 vs BPM 版

至少 8 個模組同時存在兩支 Action：

```
AbortProcessAction          ←→  BpmAbortProcessAction
CreateProcessDocumentAction ←→  BpmCreateProcessDocumentAction
DealDoneWorkItemAction      ←→  BpmDealDoneWorkItemAction
ManageDraftAction           ←→  BpmManageDraftAction
RedoInvokeAction            ←→  BpmRedoInvokeAction
SearchFormDataAction        ←→  BpmSearchFormDataAction
ValidateProcessAction       ←→  BpmValidateProcessAction
ProcessTracer               ←→  BpmProcessTracer
ProcessPreviewer            ←→  BpmProcessPreviewer
IntegratePortalURLEntranceAction ←→ BpmIntegratePortalURLEntranceAction
```

`struts-common-config.xml` 裡有多處 `<!--Gaspard remove for Merge v6 ... -->` 註解，說明這是
**EFGP 原始產品與鼎新 BPM 版本合併（Merge v6）留下的痕跡**。查問題時要確認實際走的是哪一支。

### 5.2 客製化的掛載點

| 位置 | 說明 |
|---|---|
| `ajax_CustomModuleAccessor`（DWR） | 客製 JS 呼叫後端的官方管道 |
| `CustomJsLib\`、`CustomCssLib\`、`CustomImage\` | 前端資源 |
| `CustomModule\`、`CustomOpenWin\` | 客製頁面 |
| `CustomMultilanguage\` | 客製多語系 |
| `modules\NaNa\conf\NaNaPlugIn.xml` | 後端 EJB 方法前後掛 handler（目前停用） |
| `modules\NaNa\lib\custom\main\` | 客製 jar 放置處（目前只有 module.xml） |

> 貴公司的 `ISOMod.js` 就是走 `ajax_IsoModuleAccessor` + `ajax_CustomModuleAccessor` 這條路。

### 5.3 安全過濾白名單

`NaNaWeb.properties` 定義了**繞過安全驗證**的 URL：

- `actionFilter.ignore.urlToken.*` — 20 條，含 `/Authentication`、`/ExtraLogin`、`/Adapter`、`/ToolSuite`、`/MobileOpenPortalService`
- `jspFilter.ignore.urlToken.*` — 22 條，含 `/dwr`、`/webservice/servlet/AxisServlet`、`/customization`、`/ISOModule`、`/BPMModule/`

> `/dwr` 與 `AxisServlet` 在 JSP 過濾白名單中，代表 **DWR 與 SOAP 端點的授權檢查是在各自服務內部做的**，不經過 JSP filter。若要稽核權限，這兩處要單獨檢視。

---

## 六、怎麼用這張圖

| 目的 | 從哪裡下手 |
|---|---|
| **查某個畫面的後端邏輯** | 從瀏覽器 URL 取 `/GP/<模組>/<action>` → 對照第二節找 Action 類別 → 反編譯或看 log |
| **查前端 AJAX 行為** | 看 JSP 引入哪支 `ajax_*.js` → 對照第四節找後端 helper 類別 |
| **加客製功能** | 走 5.2 的掛載點，不要動原廠檔案 |
| **追某個錯誤** | 在 `NaNaApp.log` 搜 Action 類別名，stack trace 會顯示完整呼叫鏈 |
| **盤點對外介面** | 第一節的 servlet 表 + 5.3 的白名單 |

### 建議的下一層

1. **`PerformWorkItem` 的 26 條路由**——這是簽核流程的心臟，值得單獨展開 `hdnMethod` 的所有值
2. **`dwr-default.xml` 的方法層級白名單**——目前只列了類別，每個類別實際開放哪些方法還沒展開
3. **`server-config.wsdd`（9 KB）**——SOAP 對外介面清單，是與其他系統整合的契約
