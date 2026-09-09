# BPM ↔ ERP 整合介面清冊

> 建立日期：2026-09-07
> 來源：`nana-app.ear/nana-services-server.jar`（2,765 類別）、`NaNaWeb.war/WEB-INF/server-config.wsdd`、`WEB-INF/classes`
> 方法：`javap` 反組譯介面簽章（未反編譯實作內容）
> 姊妹文件：[BPM系統分析.md](BPM系統分析.md)、[BPM系統地圖.md](BPM系統地圖.md)

---

## 一、總覽：有多少指令跟 ERP 對接

整合程式碼共 **456 個類別 / 20 個子套件**，分兩個方向：

| 方向 | 機制 | 指令數 |
|---|---|---|
| **BPM → ERP**（Call Out） | EJB Session Bean，在流程設計師裡設定呼叫 | **87** 個核心 ERP 方法 |
| **ERP → BPM**（Call In） | SOAP Web Service（Apache Axis） | **35** 個白名單方法 + **143** 個全開放方法 |

### 核心 ERP 指令（BPM → ERP）87 個

| 介面 | 對接對象 | 方法數 |
|---|---|---|
| `TiptopManager` | **TIPTOP ERP（舊版）** | **47** |
| `TiptopManagerForStaffAttendance` | TIPTOP 差勤 | 2 |
| `NewTiptopManager` | **T100 ERP（新版）** | 16 |
| `BpmServiceAPI` | T100 流程服務 | 8 |
| `NewTiptopSecurityManager` | T100 安全 | 1 |
| `SapXmlManager` | **SAP** | 13 |

### 延伸整合（同屬鼎新產品線）90 個

| 介面 | 對接對象 | 方法數 |
|---|---|---|
| `CrmManager` | CRM | 44 |
| `AppFormManager` | AppForm 表單應用 | 34 |
| `IWCManager` | IWC | 5 |
| `EasyFlowManager` | EasyFlow | 4 |
| `McloudManager` | 鼎新 MCloud | 3 |

> 另有 `MobileManager`(60)、`AdapterManager`(30)、`PortalManager`(1)、`WarRoomManager`(2)、`WorkflowManager`(5)，屬行動與入口整合，非 ERP。

---

## 二、支援的 ERP 品牌

從 `SystemIntegration` 的方法命名可以看出，同一套 BPM 支援多品牌 ERP 的狀態回寫：

| 品牌 | 方法組 |
|---|---|
| **TIPTOP** | `processAgreed` / `processDisAgreed` / `processAborted`（TiptopManager） |
| **T100** | `BpmServiceAPI.processAgreed` 等 |
| **WFERP** | `processAgreedWFERP` / `processDisAgreedWFERP` / `processAbortedWFERP` |
| **易飛 YIFE** | `processAgreedYIFE` / `processDisAgreedYIFE` / `processAbortedYIFE` |
| **Cosmos** | `processAgreedCosmos` / `processDisAgreedCosmos` / `processAbortedCosmos` |
| **SAP** | `SapXmlManager.invokeToSap` |
| **PLM** | `PLMIntegrationEFGP` |
| **DotJ** | `DotJIntegration` |

> 本站實際使用的是 **TIPTOP**（見第六節故障案例）。

---

## 三、方向一：BPM → ERP（設計師可呼叫）

在流程設計師的「Session Bean Configuration」裡設定，JNDI 格式：

```
java:global/nana-app/nana-services-server/<BeanName>!<介面全名>
例：
java:global/nana-app/nana-services-server/TiptopManagerBean!com.dsc.nana.services.sysintegration.tiptop.TiptopManager
```

### 3.1 TiptopManager（47 個方法）

**流程狀態回寫**——最常用，都吃流程序號（processInstanceSN）：

| 方法 | 送出的狀態碼 | 用途 |
|---|---|---|
| `processInvoked(String)` | `1` INVOKED | 流程啟動 |
| `processAborted(String)` | `2` ABORTED | 流程中止 |
| **`processAgreed(String)`** | **`3` AGREED** | **簽核同意** |
| `processDisAgreed(String)` | `4` DISAGREED | 簽核不同意 |
| `processCancelled(String)` | `5` CANCELLED | 取消 |
| `processCompleted(String)` | — | 流程完成 |
| `processTerminated(String)` | — | 流程終止 |
| `setStatus(String, TiptopStatus)` | 自訂 | 直接指定狀態 |

每個 `process*` 方法都有 4 種多載：

```java
processAgreed(String 流程序號)
processAgreed(String 流程序號, String)
processAgreed(String 流程序號, Integer)
processAgreed(String 流程序號, String, Integer)
processAgreedReturnMessage(String)          // 回傳訊息版本
processAgreedReturnMessage(String, Integer)
```

**表單操作**

| 方法 | 用途 |
|---|---|
| `createForm(Object)` | 建立表單 |
| `doCreateForm(String)` | 執行建單 |
| `columnSet(Object)` | 欄位設定 |
| `getTemplateFormFieldDef(String)` | 取範本欄位定義 |
| `getFormFlow(Object)` | 取表單流程 |

**查詢**

| 方法 | 用途 |
|---|---|
| `getApproveOpinion(Object)` | 簽核意見 |
| `getProgramID(String, String, String)` | 取 TIPTOP 程式代號 |
| `getTiptopFileData(String×4)` | 取 TIPTOP 檔案（回傳 byte[]） |
| `getTiptopResource(String×4)` | 取資源（回傳 HashMap） |
| `getWebServicesApplicationByMethodName(String)` | 依方法名找應用定義 |
| `getWebServicesApplicationByOID(String)` | 依 OID 找應用定義 |

**維運**

`testEJB`、`getModel`、`updateModel`、`reloadModel`、`isSysExisted`、`isSysExistedWith`、
`correctMappingSet`、`getCacheInfo`、`removeCacheInfo`、`runMethod`

**Local 介面額外提供**（`TiptopManagerLocal`，38 個）

`updateRelevantDataForNewTransaction(String, Map)`、`callTTWebService(Map)`

### 3.2 NewTiptopManager — T100（16 個方法）

```
createErrorRecordForNewTransaction   deleteSysintegrationServer   dontDoAnything
findPurchaseUsers                    generateApproveLogGet        generateGetTypeServiceXML
generateProcessTypeServiceXML        getImaf142s                  getSysT100Config
getSysintegrationServer              getSysintegrationServerByOID noticeSupplier
testT100Jboss                        transferInvokeProcess        updateSysT100Config
updateSysintegrationServer
```

### 3.3 BpmServiceAPI — T100 流程服務（8 個方法）

```
bpmGateWay   customerNotifyProcess   processAborted   processAgreed
processAgreedReturnMessage           processDisAgreed
```

### 3.4 SapXmlManager — SAP（13 個方法）

| 分類 | 方法 |
|---|---|
| 呼叫 | `invokeToSap`、`connectToSapByAjax`、`testSapConnection` |
| 連線管理 | `UpdateSapConnection`、`delSapConnection`、`getSapConnectionByDest`、`getSapConnectionList` |
| 表單對映 | `insertSapFormMapping`、`updateSapFormMapping`、`delSapMappingByOID`、`getSapFormMappingByID`、`getSapFormMappingByOID`、`getSapFormMappingList` |

---

## 四、方向二：ERP → BPM（SOAP Web Service）

端點：`http://<host>/NaNaWeb/webservice/servlet/AxisServlet`
命名空間：`http://webservice.nana.dsc.com/`
實作類別：`com.dsc.nana.user_interface.web.webservice.*`

| 服務名稱 | 開放範圍 | 實際方法數 |
|---|---|---|
| `TipTopIntegration` | 白名單 5 | （類別共 39 個 public） |
| `SystemIntegration` | 白名單 16 | （類別共 38 個 public） |
| `DotJIntegration` | 白名單 9 | （類別共 41 個 public） |
| `AppFormIntegrationEFGP` | 白名單 4 | （類別共 8 個 public） |
| `CrmIntegrationEFGP` | 白名單 1 | （類別共 8 個 public） |
| `WorkflowService` | **全開放 `*`** | **66** |
| `MOfficeIntegrationEFGP` | **全開放 `*`** | **45** |
| `PortalIntegrationEFGP` | **全開放 `*`** | **17** |
| `CrossIntegrationEFGP` | **全開放 `*`** | **8** |
| `VamIntegrationEFGP` | **全開放 `*`** | **4** |
| `PLMIntegrationEFGP` | **全開放 `*`** | **3** |
| `BpmWorkflowService` | **全開放 `*`** | （類別不在 NaNaWeb，推測在 NaNaXWeb） |
| `Version` | 1 | Axis 內建版本查詢 |

### 4.1 TipTopIntegration 白名單（5 個）

```
EasyFlowGPGateWay          invokeTiptopCreateForm     getTiptopPlantID
testTipTopWebService       checkTiptopBizLogic
```

### 4.2 SystemIntegration 白名單（16 個）

```
runMethod                  doFormCreateTIPTOP         updateFormDefinition
getFormFlowById            getApproveLogById          getStringByEncryption
invokeTipTopWebService
processAgreedWFERP         processDisAgreedWFERP      processAbortedWFERP
processAgreedYIFE          processDisAgreedYIFE       processAbortedYIFE
processAgreedCosmos        processDisAgreedCosmos     processAbortedCosmos
```

### 4.3 DotJIntegration 白名單（9 個）

```
runMethod                          invokeDotJConfirmService    invokeDotJProcessResetService
getCustomModuleUserInfoCache       validateModuleLicense       fetchFormInstanceWithProcSerlNo
updateFormValueBySerialNember      getSysintegrationServer     loadResourceBundle
```

### 4.4 AppFormIntegrationEFGP 白名單（4 個）

```
EasyFlowGPGateWay   insertemsmb   getFormStateAndResult   EFGPSyncOrgGateWay
```

---

## 五、指令派送機制（Method Dispatcher）

TIPTOP / T100 / CRM 三組都用同一種 Command 模式：`MethodDispatcher` 收到 XML 請求後，依 `RequestType` 派送到對應的 `Method*` 類別。共 **23 個指令類別**：

### TIPTOP（10 個）

| 類別 | 大小 | 對應指令 |
|---|---|---|
| `MethodCreateForm` | **129 KB** | 建立表單（最大的一支） |
| `MethodSetStatus` | 29 KB | **設定狀態（processAgreed 走這裡）** |
| `MethodDoFormCreate` | 27 KB | 執行建單 |
| `MethodColumnSet` | 16 KB | 欄位設定 |
| `MethodGetFormInfo` | 11 KB | 取表單資訊 |
| `MethodDispatcher` | 9 KB | 派送器 |
| `MethodGetApproveLog` | 7 KB | 簽核記錄 |
| `MethodGetProgramID` | 4 KB | 取程式代號 |
| `MethodGetApproveOpinion` | 4 KB | 簽核意見 |
| `MethodGetFormFlow` | 3 KB | 表單流程 |

### T100 / newtiptop（5 個）

| 類別 | 大小 | 對應指令 |
|---|---|---|
| `MethodProcessCreate` | **68 KB** | 建立流程 |
| `MethodProcessStatusUpdate` | 28 KB | 流程狀態更新 |
| `MethodWorkItemGet` | 19 KB | 取待辦 |
| `MethodCustomerNotifyProcess` | 7 KB | 客戶通知 |
| `MethodProcessInfoGet` | 5 KB | 取流程資訊 |

另有 `InvokeT100Process`（47 KB）負責實際呼叫。

### CRM（8 個）

`MethodCreateForm`、`MethodSetStatus`、`MethodColumnSet`、`MethodGetFormFlow`、
`MethodGetApproveOpinion`、`MethodGetProgramID`、`MethodOpenDocument`、`MethodDispatcher`

---

## 六、目前的故障案例（2026-09-07 實測）

### 案例：`PorcessAgreedForTiptop`（APP116840009170310）

流程設計師中定義的 Session Bean 應用：

| 欄位 | 值 |
|---|---|
| 應用 ID | `APP116840009170310` |
| 名稱 | `PorcessAgreedForTiptop`（原文即拼錯，Porcess） |
| JNDI | `java:global/nana-app/nana-services-server/TiptopManagerBean!...TiptopManager` |
| 函式 | `processAgreed` |
| 參數 | `pProcessInstanceSN`（IN）← `[processSerialNumber]流程序號` |

### 呼叫鏈

```
自動關卡 AutoAgent（每小時 :24 執行）
  → WorkflowEngineBean.performWorkItemByAutoAgent
  → 應用 APP116840009170310
  → TiptopManagerBean.processAgreed(流程序號)
  → setStatus(流程序號, TiptopStatus.AGREED)   ← 狀態碼 3
  → MethodSetStatus → SOAP → TIPTOP
  → TipTopCreatedFormInstances.removeByValue() ← 清快取
```

### 結果：全數失敗

`Tiptop.log`（2026-09-07 當日）：

| 項目 | 數量 |
|---|---|
| SetStatus 回應總數 | 80 |
| 成功 `ReturnStatus=Y` | **0** |
| 失敗 `ReturnStatus=N` | **80** |

`NaNaApp.log` 中 `APP116840009170310` 出現 9 次，00:24～08:24 每小時一次，全部是：

```
ERROR [WorkflowEngineBean.performWorkItemByAutoAgent:3045]
  Error occurred while executing the application(id=APP116840009170310)
```

### 錯誤內容（原始為 Big5，已解碼）

```xml
<Response>
  <ResponseType>SetStatus</ResponseType>
  <ResponseInfo>
    <SenderIP>GSMC-TIPTOPGP</SenderIP>
    <ReceiverIP>10.10.112.68</ReceiverIP>
  </ResponseInfo>
  <ResponseContent>
    <ReturnInfo>
      <ReturnStatus>N</ReturnStatus>
      <ReturnDescribe>DS67 aws-083 資料庫連接失敗</ReturnDescribe>
    </ReturnInfo>
  </ResponseContent>
</Response>
```

**錯誤來自 TIPTOP 端**（`GSMC-TIPTOPGP`），代碼 `aws-083`，DS63 與 DS67 兩個廠別的資料庫連不上。BPM 這邊的呼叫是正常送出的。

### 卡住的單據

| 單號 | 廠別 | TIPTOP 程式 | BPM 流程序號 |
|---|---|---|---|
| `CTZA-2601000001` | DS63 | `axmt400` | `1f402558f82110048e16b8eede1c8b55` |
| `PMZC-2604000002` | DS67 | `apmi610` | `44b1b12cf8de10048e54e9fb942f892e` |

BPM 已簽核完成但狀態回寫不到 ERP，AutoAgent 每小時無限重試。

單號前四碼是年月（`2601` = 2026年1月、`2604` = 2026年4月），推估已卡 5～8 個月。**確切起始日無法確認**——歷史 log 已於 2026-09-07 清理。

---

## 七、設定與檔案位置

| 項目 | 位置 |
|---|---|
| TIPTOP 整合設定 | `modules\NaNa\conf\NaNaIntSys.properties` |
| ERP 資料庫連線 | `modules\NaNa\conf\epm\ERP.hibernate.cfg.xml`（Oracle，**明文帳密**） |
| SOAP 服務定義 | `standalone\deployments\NaNaWeb.war\WEB-INF\server-config.wsdd` |
| EJB 實作 | `standalone\deployments\nana-app.ear` → `nana-services-server.jar` |
| Web Service 實作 | `NaNaWeb.war\WEB-INF\classes\com\dsc\nana\user_interface\web\webservice\` |
| 整合設定畫面 | `/GP/WMS/Sysintegration`、`/GP/WMS/ManageSysIntegration` |
| ERP 相關 log | `modules\NaNa\log\Tiptop.log` |
| 前端 AJAX | `ajax_TiptopAccessor`、`ajax_SapAccessor`、`ajax_MCloudAccessor` |

---

## 八、值得注意的地方

### 8.1 SOAP 端點不經過 JSP 安全過濾

`NaNaWeb.properties` 的白名單包含：

```
jspFilter.ignore.urlToken.6=/webservice/servlet/AxisServlet
```

代表 AxisServlet 不經過 JSP filter，**授權檢查由各 Web Service 類別自行負責**。

其中 6 個服務設為 `allowedMethods="*"`（全開放），合計對外暴露 **143 個方法**——最大的 `WorkflowService` 有 66 個。這些類別的 public 方法裡包含 `setEfgpHostIP`、`setSystemIntegratedIp` 這類設定型方法。

建議：確認這些端點是否只在內網開放，或改為明確的方法白名單（如 TipTopIntegration / SystemIntegration 的做法）。

### 8.2 舊版與新版 TIPTOP 並存

`tiptop`（50 類別）與 `newtiptop`（28 類別）是兩套獨立實作。舊版走 `TIPTOPGateWay` SOAP stub，新版走 `InvokeT100Process`。設定新應用時要確認對接的是哪一代 ERP。

### 8.3 失敗沒有告警機制

AutoAgent 失敗只寫 log、不通知任何人，也不會停止重試。目前兩張單已卡數個月無人察覺。建議對 `Tiptop.log` 的 `ReturnStatus=N` 建立監控。
