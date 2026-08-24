# 鼎新 BPM WorkflowService API 手冊

| 項目 | 值 |
|:---|:---|
| Endpoint | `http://10.10.130.191:8080/NaNaWeb/services/WorkflowService` |
| 方法總數 | 65 |
| 已寫下語意 | 39 |
| 實測成功 | 29 |
| 實測時間 | 2026-08-24T08:56:02 |

本手冊由 `build_manual.py` 合成，勿直接編輯 ——
語意註記請改 `notes.json`，介面契約與實測結果由工具重跑產生。

> **190 正式區未曾連線。** 以下全部來自 191 測試區。

## 呼叫前必讀

### 這是 rpc/encoded，不是 document/literal

Apache Axis 1.3 產生的舊式 SOAP。實務上的三個後果：

1. **參數是位置對應**，順序錯了不會報錯，只會拿到錯的結果或空值。
   正確順序看每支方法的 `parameterOrder`（本手冊列出的順序已經是對的）。
2. **`SOAPAction` 是空字串**，分派靠 body 內的方法名。
3. **Python 的 zeep 接不上這個服務**（不支援 SOAP encoding）。
   本專案用 `ws_client.py` 手刻 envelope；Node 端的 `soap` 套件則可正常運作。

envelope 長這樣：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <ns1:findFormOIDsOfProcess xmlns:ns1="http://webservice.nana.dsc.com/">
      <pProcessPackageId xsi:type="xsd:string">SP_DetectionOPProcess</pProcessPackageId>
    </ns1:findFormOIDsOfProcess>
  </soapenv:Body>
</soapenv:Envelope>
```

### 回傳的 `string` 幾乎都不是純字串

41 支方法宣告回傳 `string`，實際內容有四種，**WSDL 完全看不出來**：

| 實際內容 | 例子 |
|:---|:---|
| XStream 序列化的 Java 物件 XML | `fetchProcInstances`、`fetchOrgUnitOfUserId` |
| 屬性式 XML（風格不同） | `getSubstituteState` |
| 逗號分隔字串 | `fetchCanTraceProcSN` |
| 純量文字 | `findFormOIDsOfProcess`、`fetchProcessContextVariable`（三參數版） |

`fetchFormInstance*` 更是「XML 字串包在 XML 裡」，`fieldValues` 要解兩層。

### 失敗有三種，其中一種不會丟例外

| 型態 | 表現 | 呼叫端要做什麼 |
|:---|:---|:---|
| SOAP Fault | HTTP 500，`faultstring` 帶 Java 例外 | 正常攔截 |
| 業務性拒絕 | 也是 Fault，但訊息講得很清楚（例如「單子還在跑，沒有作廢意見」） | 讀訊息，別一律當系統錯誤 |
| **假成功** | **HTTP 200，回傳字串本身是 `<NotFoundException>...</NotFoundException>`** | **必須額外檢查回傳內容** |

第三種目前已知發生在 `findManagerByAppLvl`。只判斷有無丟例外的呼叫端會把
例外訊息當成資料收下。

### 表單欄位值（`pFormFieldValue`）的格式

開單時 `pFormFieldValue` 是一段 XML 字串，以表單 ID 為根，每個欄位一個標籤：

```xml
<SP_DetectionOPForm>
  <EmailSubjectTextBox id="EmailSubjectTextBox" dataType="java.lang.String" perDataProId="">主旨</EmailSubjectTextBox>
  <ControlPlanApplyDate id="ControlPlanApplyDate" dataType="java.util.Date">2026/08/24</ControlPlanApplyDate>
</SP_DetectionOPForm>
```

存進去之後由 `fetchFormInstance*` 讀回來時是同樣的結構，已實測來回一致。

### 已知地雷：錯的欄位 id 不會被擋，會延後爆炸

`invokeProcess` **不驗證** `pFormFieldValue` 裡的欄位 id 是否存在於表單定義。
不存在的欄位照樣寫進單子，開單成功、回傳正常。等到有人呼叫
`fetchUniFormatFormInstanceWithProcSerlNo` 讀這張單時才會炸：

```
java.lang.IllegalArgumentException:
Argument 'pFieldId = EmailSubjectTextBox' cannot find ElementDefinition in FormDefinition.
```

而 `fetchFormInstanceWithProcSerlNo`（非 UniFormat 版）讀同一張單卻毫無問題 ——
所以這種壞單可能很久都不會被發現。

**開單前先用 `getFormFieldTemplate(pFormDefOID)` 對過欄位 id。**

---

## 方法索引

| 方法 | 信心 | 實測 |
|:---|:---|:---|
| `abortProcessForSerialNo` | ⚠️ 未實測，僅推測 | 未實測 |
| `acceptWorkItem` | ⚠️ 尚未分析 | 未實測 |
| `addCloneSerialActivity` | ⚠️ 尚未分析 | 未實測 |
| `addCustomActivity` | ⚠️ 尚未分析 | 未實測 |
| `addCustomParallelActivity` | ⚠️ 尚未分析 | 未實測 |
| `addCustomParallelAndSerialActivity` | ⚠️ 尚未分析 | 未實測 |
| `addCustomParallelAndSerialActivity` | ⚠️ 尚未分析 | 未實測 |
| `addLabelToNoticeWorkItem` | ⚠️ 尚未分析 | 未實測 |
| `addUserAbsence` | ⚠️ 尚未分析 | 未實測 |
| `assignRelevantDataBySerialNo` | ⚠️ 尚未分析 | 未實測 |
| `assigneeReassignWorkItem` | ⚠️ 尚未分析 | 未實測 |
| `bypassActivity` | ⚠️ 尚未分析 | 未實測 |
| `checkWorkItemState` | ✅ 已實測 | 實測成功 |
| `completeWorkItem` | ⚠️ 未實測，僅推測 | 未實測 |
| `countWorkingDays` | ✅ 已實測 | 實測成功 |
| `countWorkingTime` | ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） |
| `fetchCanTraceProcSN` | ✅ 已實測 | 實測成功 |
| `fetchClosedProcInstances` | ✅ 已實測 | 實測成功 |
| `fetchDefaultSubstituteInfo` | ✅ 已實測 | 實測成功 |
| `fetchDefaultSubstituteInfo` | ✅ 已實測 | 實測成功 |
| `fetchDueDate` | ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） |
| `fetchFormInstanceWithProcOID` | ✅ 已實測 | 實測成功 |
| `fetchFormInstanceWithProcSerlNo` | ✅ 已實測 | 實測成功 |
| `fetchFullProcInstanceWithOID` | ✅ 已實測 | 實測成功 |
| `fetchFullProcInstanceWithSerialNo` | ✅ 已實測 | 實測成功 |
| `fetchFullProcInstanceWithSerialNoShowReferences` | ✅ 已實測 | 實測成功 |
| `fetchOrgUnitOfUserId` | ☑️ 已在既有服務驗證 | 實測成功 |
| `fetchProcInstanceWithOID` | ✅ 已實測 | 實測成功 |
| `fetchProcInstanceWithSerialNo` | ✅ 已實測 | 實測成功 |
| `fetchProcInstances` | ✅ 已實測 | 實測成功 |
| `fetchProcSNMatchCurrtentPerformer` | ✅ 已實測 | 實測成功 |
| `fetchProcessAbortOrTerminateComment` | ✅ 已實測 | 實測成功 |
| `fetchProcessContextVariable` | ✅ 已實測 | 實測成功 |
| `fetchProcessContextVariable` | ✅ 已實測 | 實測成功 |
| `fetchToDoWorkItem` | ✅ 已實測 | 實測成功 |
| `fetchUniFormatFormInstanceWithProcOID` | ✅ 已實測 | 實測成功 |
| `fetchUniFormatFormInstanceWithProcSerlNo` | ✅ 已實測 | 實測成功 |
| `fetchWorkItemCount` | ✅ 已實測 | 實測成功 |
| `findFormOIDsOfProcess` | ☑️ 已在既有服務驗證 | 實測成功 |
| `findManagerByAppLvl` | ⚠️ 未實測，僅推測 | 未實測 |
| `getFormFieldTemplate` | ✅ 已實測 | 實測成功 |
| `getProcessPackage` | ✅ 已實測 | 實測成功 |
| `getProjectsWithOrganizationId` | ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） |
| `getSubstituteState` | ✅ 已實測 | 實測成功 |
| `getSysintegrationServer` | ✅ 已實測 | 實測成功 |
| `importOrganizationData` | ⚠️ 尚未分析 | 未實測 |
| `increaseViewTimesOfWorkAssignment` | ⚠️ 尚未分析 | 未實測 |
| `invokeProcess` | ☑️ 已在既有服務驗證 | 未實測 |
| `invokeProcess` | ☑️ 已在既有服務驗證 | 未實測 |
| `invokeProcessAndAddCustAct` | ⚠️ 尚未分析 | 未實測 |
| `invokeProcessAndAddCustActByOrg` | ⚠️ 尚未分析 | 未實測 |
| `invokeProcessByOrg` | ⚠️ 未實測，僅推測 | 未實測 |
| `invokeProcessByOrg` | ⚠️ 未實測，僅推測 | 未實測 |
| `invokeProcessByParameter` | ⚠️ 尚未分析 | 未實測 |
| `invokeProcessByParameterByOrg` | ⚠️ 尚未分析 | 未實測 |
| `isPerformerOfProcessInstance` | ✅ 已實測 | 實測成功 |
| `managementChangeWorkItemOwner` | ⚠️ 尚未分析 | 未實測 |
| `managementReassignWorkItem` | ⚠️ 尚未分析 | 未實測 |
| `reexecuteActivity` | ⚠️ 尚未分析 | 未實測 |
| `removeAbsenceRecord` | ⚠️ 尚未分析 | 未實測 |
| `removeLabelFromNoticeWorkItem` | ⚠️ 尚未分析 | 未實測 |
| `reserveNoCmDocument` | ⚠️ 尚未分析 | 未實測 |
| `terminatedProcessForSerialNo` | ⚠️ 尚未分析 | 未實測 |
| `updateDefaultSubstitute` | ⚠️ 尚未分析 | 未實測 |
| `updateFormValueBySerialNember` | ⚠️ 尚未分析 | 未實測 |

---

## 已分析的方法

### abortProcessForSerialNo

```
abortProcessForSerialNo(string pProcessInstanceSerialNo, string pAbortComment) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 未實測 | — |

**用途**：作廢流程單。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 單號 |
| `pAbortComment` | string | 作廢原因 |

**回傳**：void。

> 作廢後的意見可由 fetchProcessAbortOrTerminateComment 讀回（該方法已實測到「取回重辦」這類文字）。

### checkWorkItemState

```
checkWorkItemState(string pWorkItemOID) : int
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 219 ms |

**用途**：查工作項目狀態。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItemOID` | string | 由 fetchToDoWorkItem 取得 |

**回傳**：int。待簽中的工作項目實測回 0。

> 其餘狀態碼對應的意義未驗證 —— 需要已完成／已轉派的工作項目才測得出來。

回傳樣本：`out/payloads/checkWorkItemStateRequest.xml`

### completeWorkItem

```
completeWorkItem(string pWorkItemOID, string pUserId, string pComment) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 未實測 | — |

**用途**：簽核完成一個工作項目。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItemOID` | string | 工作項目 OID |
| `pUserId` | string | 簽核者 |
| `pComment` | string | 簽核意見 |

**回傳**：void。

> 會推動流程往下一關，需搭配可拋棄的測試單驗證。

### countWorkingDays

```
countWorkingDays(string pUserId, string pStartDateTime, string pEndDateTime, string pDateFormat) : int
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 38 ms |

**用途**：依工作行事曆計算區間內的工作日數。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pStartDateTime` | string | 起 |
| `pEndDateTime` | string | 迄 |
| `pDateFormat` | string | Java SimpleDateFormat 語法，例如 yyyy/MM/dd HH:mm:ss |

**回傳**：int。

> 實測 S112009 在 2026/08/01～08/24 回 0，且同參數的 countWorkingTime 拋 NotFoundException —— 研判是該帳號沒有掛工作行事曆，不是方法壞掉。要驗證需先找一個有行事曆的帳號。

回傳樣本：`out/payloads/countWorkingDaysRequest.xml`

### countWorkingTime

```
countWorkingTime(string pUserId, string pStartDateTime, string pEndDateTime, string pDateFormat) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） | 74 ms |

**用途**：依工作行事曆計算區間內的工作時數。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 未確認 |
| `pStartDateTime` | string | 未確認 |
| `pEndDateTime` | string | 未確認 |
| `pDateFormat` | string | 同 countWorkingDays |

**回傳**：string。

> 實測拋 NotFoundException，與 countWorkingDays 回 0 相互印證是帳號無行事曆。未取得成功樣本。

實測錯誤：`java.rmi.RemoteException: User.countWorkingTime() throwed exception 'com.dsc.nana.domain.NotFoundException'`

### fetchCanTraceProcSN

```
fetchCanTraceProcSN(string pProcessIds, string pUserId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 43 ms |

**用途**：查某人有權追蹤（檢視）的單號清單。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessIds` | string | 流程 ID |
| `pUserId` | string | 員工編號 |

**回傳**：**逗號分隔的單號字串**，不是 XML。實測末尾帶逗號。

> 回傳格式與其他 fetch* 完全不同，解析時要特判。

回傳樣本：`out/payloads/fetchCanTraceProcSNRequest.xml`

### fetchClosedProcInstances

```
fetchClosedProcInstances(string pProcessId, string pProcessClosedStartTime, string pProcessClosedEndTime, string pProcInstanceClosedState) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 559 ms |

**用途**：同上，但時間區間比對的是結案時間。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessId` | string | 未確認 |
| `pProcessClosedStartTime` | string | 結案時間起 |
| `pProcessClosedEndTime` | string | 結案時間迄 |
| `pProcInstanceClosedState` | string | 空字串為全部 |

**回傳**：同 fetchProcInstances 的結構。

回傳樣本：`out/payloads/fetchClosedProcInstancesRequest.xml`

### fetchDefaultSubstituteInfo

```
fetchDefaultSubstituteInfo(string pUserId, int pStartSeq, int pEndSeq, string pDate) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 80 ms |

**用途**：查預設代理人設定。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pStartSeq` | int | int，序號起 |
| `pEndSeq` | int | int，序號迄 |
| `pDate` | string | 四參數多載才有，指定查詢基準日 |

**回傳**：DefaultSubstituteList，含 description 與 defSubs。

> 查無資料時 description 是英文說明句（no default substitute found in range...），不是空值 —— 呼叫端不要把它當資料顯示。

回傳樣本：`out/payloads/fetchDefaultSubstituteInfoRequest.xml`

### fetchDefaultSubstituteInfo（多載：3 參數）

```
fetchDefaultSubstituteInfo(string pUserId, int pStartSeq, int pEndSeq) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 53 ms |

**用途**：查預設代理人設定。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pStartSeq` | int | int，序號起 |
| `pEndSeq` | int | int，序號迄 |

**回傳**：DefaultSubstituteList，含 description 與 defSubs。

> 查無資料時 description 是英文說明句（no default substitute found in range...），不是空值 —— 呼叫端不要把它當資料顯示。

回傳樣本：`out/payloads/fetchDefaultSubstituteInfoRequest1.xml`

### fetchDueDate

```
fetchDueDate(string pUserId, string pBaseDate, string pDueDays, string pDateFormat) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） | 47 ms |

**用途**：依工作行事曆推算到期日。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 未確認 |
| `pBaseDate` | string | 基準日 |
| `pDueDays` | string | 天數 |
| `pDateFormat` | string | 日期格式 |

**回傳**：string。

> 同上，拋 NotFoundException。

實測錯誤：`java.rmi.RemoteException: User.fetchDueDate() throwed exception 'com.dsc.nana.domain.NotFoundException'`

### fetchFormInstanceWithProcOID

```
fetchFormInstanceWithProcOID(string pProcessInstanceOID) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 353 ms |

**用途**：同上，改用 OID。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceOID` | string | 流程實例 OID |

**回傳**：與單號版相同。

回傳樣本：`out/payloads/fetchFormInstanceWithProcOIDRequest.xml`

### fetchFormInstanceWithProcSerlNo

```
fetchFormInstanceWithProcSerlNo(string pProcessInstanceSerialNo) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 386 ms |

**用途**：只取表單欄位值，不含簽核歷程。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 單號 |

**回傳**：FormInfo，fieldValues 內是逸出後的 <表單ID><欄位 id=... >值</欄位></表單ID>。

> fieldValues 是「XML 字串包在 XML 裡」，要解兩層。

回傳樣本：`out/payloads/fetchFormInstanceWithProcSerlNoRequest.xml`

### fetchFullProcInstanceWithOID

```
fetchFullProcInstanceWithOID(string pProcessInstanceOID) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 376 ms |

**用途**：同上，改用 OID 查。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceOID` | string | 流程實例 OID |

**回傳**：與單號版相同。

回傳樣本：`out/payloads/fetchFullProcInstanceWithOIDRequest.xml`

### fetchFullProcInstanceWithSerialNo

```
fetchFullProcInstanceWithSerialNo(string pProcessInstanceSerialNo) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 376 ms |

**用途**：取完整流程單：單頭 + 表單欄位值 + 每個關卡的簽核歷程。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 單號 |

**回傳**：ProcessInfo > forms(FormInfo) + ActInstanceInfo > PerformInfo > PerformDetail，含 activityId、performerName、performedTime、comment、state。

> 要一次拿到「誰簽的、簽了什麼」就用這支。關卡狀態實測值：closed.completed、open.running.not_performed。

回傳樣本：`out/payloads/fetchFullProcInstanceWithSerialNoRequest.xml`

### fetchFullProcInstanceWithSerialNoShowReferences

```
fetchFullProcInstanceWithSerialNoShowReferences(string pProcessInstanceSerialNo, boolean pShowReferences) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 420 ms |

**用途**：同 fetchFullProcInstanceWithSerialNo，多一個 pShowReferences 開關。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 未確認 |
| `pShowReferences` | boolean | boolean。實測傳 true 時回傳與不帶此參數的版本完全相同 |

**回傳**：同上。

> pShowReferences 的實際作用在測試流程上看不出差異 —— 可能要有跨流程引用的單子才會有分別。未確認。

回傳樣本：`out/payloads/fetchFullProcInstanceWithSerialNoShowReferencesRequest.xml`

### fetchOrgUnitOfUserId

```
fetchOrgUnitOfUserId(string pUserId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ☑️ 已在既有服務驗證 | 實測成功 | 49 ms |

**用途**：查使用者所屬部門，開單要用的 pOrgUnitId 從這裡來。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |

**回傳**：OrganizationUnitCollection，內含 OID / id / name / orgUnitType / orgName / isMain。

回傳樣本：`out/payloads/fetchOrgUnitOfUserIdRequest.xml`

### fetchProcInstanceWithOID

```
fetchProcInstanceWithOID(string pProcessInstanceOID) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 128 ms |

**用途**：同 fetchProcInstanceWithSerialNo，改用 OID 查。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceOID` | string | 流程實例 OID |

**回傳**：與單號版完全相同（實測兩者位元組一致）。

回傳樣本：`out/payloads/fetchProcInstanceWithOIDRequest.xml`

### fetchProcInstanceWithSerialNo

```
fetchProcInstanceWithSerialNo(string pProcessInstanceSerialNo) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 169 ms |

**用途**：以單號取單頭資料（不含表單欄位與簽核歷程）。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 單號，例如 SP_DetectionOPProcess00000030 |

**回傳**：單筆 ProcessInfo，實測 517 字元。

回傳樣本：`out/payloads/fetchProcInstanceWithSerialNoRequest.xml`

### fetchProcInstances

```
fetchProcInstances(string pProcessId, string pProcessInitialStartTime, string pProcessInitialEndTime, string pProcInstanceState) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 527 ms |

**用途**：依流程 ID 與建立時間區間查流程單，可再依狀態篩選。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessId` | string | 流程 ID |
| `pProcessInitialStartTime` | string | 建立時間起，yyyy/MM/dd HH:mm:ss |
| `pProcessInitialEndTime` | string | 建立時間迄 |
| `pProcInstanceState` | string | 空字串表示全部。實測看到的值：open.running、closed.completed、closed.terminated |

**回傳**：SimpleProcesses > SimpleProcessInfo，含 OID、serialNo、state、requesterId、subject、createdTime。

> 取單號與 OID 的主要入口。回傳的 createdTime 是 yyyy-MM-dd HH:mm:ss.S（橫線），與輸入的斜線格式不同。

回傳樣本：`out/payloads/fetchProcInstancesRequest.xml`

### fetchProcSNMatchCurrtentPerformer

```
fetchProcSNMatchCurrtentPerformer(string pProcessId, string pActId, string pUserId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 62 ms |

**用途**：查某人目前在指定關卡待簽的單號（方法名的 Currtent 是原廠拼字錯誤）。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessId` | string | 流程 ID |
| `pActId` | string | 關卡 id，取自 fetchFullProcInstance* 的 activityId |
| `pUserId` | string | 員工編號 |

**回傳**：單號字串。實測回單一單號，多筆時的分隔方式未驗證。

回傳樣本：`out/payloads/fetchProcSNMatchCurrtentPerformerRequest.xml`

### fetchProcessAbortOrTerminateComment

```
fetchProcessAbortOrTerminateComment(string pProcessSerialNo) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 456 ms |

**用途**：取單子被作廢或終止時填的意見。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessSerialNo` | string | 單號 |

**回傳**：純文字意見。實測格式為「意見內容(員工編號-姓名)」，操作者資訊由 BPM 自動附加。

> 單子仍在跑時會拋例外並明講原因，不是回空字串。查詢前應先確認 state 為 closed.terminated。

### fetchProcessContextVariable

```
fetchProcessContextVariable(string pProcessSerialNo, string pVariableId, boolean pOnlyTextValue) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 450 ms |

**用途**：讀流程變數（RelevantData）的執行期值。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessSerialNo` | string | 單號 |
| `pVariableId` | string | 變數 id，來源為 getProcessPackage 內的 RelevantDataDefinition.id |
| `pOnlyTextValue` | boolean | 三參數多載才有。true 回純文字值，不帶此參數則回完整物件 |

**回傳**：三參數版：純文字（實測 "false"）。兩參數版：StringWorkflowRuntimeValue 的 XStream 物件，值在 stringValue。

> 兩個多載的差別已實測確認，取值請優先用三參數版。

回傳樣本：`out/payloads/fetchProcessContextVariableRequest.xml`

### fetchProcessContextVariable（多載：2 參數）

```
fetchProcessContextVariable(string pProcessSerialNo, string pVariableId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 460 ms |

**用途**：讀流程變數（RelevantData）的執行期值。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessSerialNo` | string | 單號 |
| `pVariableId` | string | 變數 id，來源為 getProcessPackage 內的 RelevantDataDefinition.id |

**回傳**：三參數版：純文字（實測 "false"）。兩參數版：StringWorkflowRuntimeValue 的 XStream 物件，值在 stringValue。

> 兩個多載的差別已實測確認，取值請優先用三參數版。

回傳樣本：`out/payloads/fetchProcessContextVariableRequest1.xml`

### fetchToDoWorkItem

```
fetchToDoWorkItem(string pProcessIds, string pUserId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 75 ms |

**用途**：查某人在指定流程上的待辦工作項目，**取得 pWorkItemOID 的唯一實測途徑**。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessIds` | string | 流程 ID，多筆的分隔方式未驗證 |
| `pUserId` | string | 員工編號 |

**回傳**：list > SimpleWorkItem，含 processSerialNumber、activityId、workItemOID。無待辦時回 <list/>。

> 查非當前簽核者會得到空清單，不是錯誤。

回傳樣本：`out/payloads/fetchToDoWorkItemRequest.xml`

### fetchUniFormatFormInstanceWithProcOID

```
fetchUniFormatFormInstanceWithProcOID(string pProcessInstanceOID) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 443 ms |

**用途**：同上，改用 OID。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceOID` | string | 流程實例 OID |

**回傳**：同上。

回傳樣本：`out/payloads/fetchUniFormatFormInstanceWithProcOIDRequest.xml`

### fetchUniFormatFormInstanceWithProcSerlNo

```
fetchUniFormatFormInstanceWithProcSerlNo(string pProcessInstanceSerialNo) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 394 ms |

**用途**：取統一格式的表單資料（FormCollection），欄位以標準結構列出而非原始字串。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 單號 |

**回傳**：FormCollection > forms > FormInfo。

> **會驗證欄位 id**。若單子裡存有表單定義中不存在的欄位，這支會拋 IllegalArgumentException 而 fetchFormInstance* 不會。見手冊「已知地雷」。

回傳樣本：`out/payloads/fetchUniFormatFormInstanceWithProcSerlNoRequest.xml`

### fetchWorkItemCount

```
fetchWorkItemCount(string pUserID, int pAccessCondition, string pViewTimesType) : int
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 100 ms |

**用途**：計算某人的工作項目數量。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserID` | string | 員工編號（注意大寫 ID，與其他方法的 pUserId 不同） |
| `pAccessCondition` | int | int，**只接受 0 或 1**，其餘拋 IllegalArgumentException。實測 0→9、1→405，推測 0 為待辦、1 為全部或已辦 |
| `pViewTimesType` | string | string。實測傳 0、1、X 結果皆同，作用不明 |

**回傳**：int。

> pAccessCondition 的 0/1 語意由數量差推測，未經確認。

回傳樣本：`out/payloads/fetchWorkItemCountRequest.xml`

### findFormOIDsOfProcess

```
findFormOIDsOfProcess(string pProcessPackageId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ☑️ 已在既有服務驗證 | 實測成功 | 91 ms |

**用途**：由流程 ID 取得該流程掛的表單定義 OID。開單前的第一步。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 流程 ID，非 OID。例如 SP_DetectionOPProcess |

**回傳**：32 碼表單定義 OID 字串。多張表單時的分隔方式未驗證（測試流程只有一張）。

> bpmbackXmlController.js 的 testCreateProcess 就是先呼叫它拿 pFormDefOID。

回傳樣本：`out/payloads/findFormOIDsOfProcessRequest.xml`

### findManagerByAppLvl

```
findManagerByAppLvl(string pUserId, string pOrgUnitOID, string pLevelName, string pApprovalLevelType, boolean pIsDeptManager) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 未實測 | — |

**用途**：依簽核層級查主管。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pOrgUnitOID` | string | 部門 OID，非部門 id |
| `pLevelName` | string | 簽核層級名稱，有效值未知 |
| `pApprovalLevelType` | string | 簽核層級類型，有效值未知 |
| `pIsDeptManager` | boolean | boolean |

**回傳**：string。

> **這支會把例外包在回傳字串裡**：傳空的層級名稱得到 HTTP 200 與 <NotFoundException>Can not found ApprovelLevel by Name:, and Type:null</NotFoundException>。呼叫端只判斷有無丟例外會誤收。有效層級名稱待查。

### getFormFieldTemplate

```
getFormFieldTemplate(string pFormDefinitionOID) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 268 ms |

**用途**：取得表單的空白欄位模板 —— **這是欄位 id 的權威來源**。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pFormDefinitionOID` | string | findFormOIDsOfProcess 的回傳值 |

**回傳**：<表單ID> 底下每個欄位一個標籤，帶 id / dataType / perDataProId 屬性。

> 組 pFormFieldValue 前應先呼叫它對欄位 id，否則錯的欄位會被靜默寫入（見手冊「已知地雷」）。

回傳樣本：`out/payloads/getFormFieldTemplateRequest.xml`

### getProcessPackage

```
getProcessPackage(string pProcessPackageId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 413 ms |

**用途**：取整包流程定義，含關卡、參與者、流程變數（RelevantDataDefinition）。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 流程 ID |

**回傳**：Hibernate/OJB 物件圖的 XStream 序列化，實測 45 萬字元。

> 回傳量極大且含 PersistentSet、SET__PROXY__CLASS__NAME 等 ORM 雜訊。只為了查流程變數 id 的話，撈 RelevantDataDefinition.id 即可，不要整包塞進前端。

回傳樣本：`out/payloads/getProcessPackageRequest.xml`

### getProjectsWithOrganizationId

```
getProjectsWithOrganizationId(string pOrganizationId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） | 72 ms |

**用途**：依公司別查專案清單。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pOrganizationId` | string | **公司別 id，不是部門 id** |

**回傳**：未驗證。

> 傳部門 id S1800 與猜測值 SOLAR 都得到 Organization cannot be found。正確值待查（可查資料庫 Organization 表）。

實測錯誤：`java.rmi.RemoteException: Organization cannot be found. Id = S1800`

### getSubstituteState

```
getSubstituteState(string pUserId, string pCheckTime) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 33 ms |

**用途**：查使用者在指定時間點的代理狀態。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pCheckTime` | string | 檢查時間點 |

**回傳**：<SubstituteState isAbsence="Y" isSettingSubstitute="N" substituteId=""/>。

> 屬性式 XML，與其他方法的 XStream 元素式風格不同。

回傳樣本：`out/payloads/getSubstituteStateRequest.xml`

### getSysintegrationServer

```
getSysintegrationServer() : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 24 ms |

**用途**：取系統整合伺服器設定。

**回傳**：實測為字串 "[]"（空清單）。

> 測試區沒有設定整合伺服器，因此看不出非空時的結構。

回傳樣本：`out/payloads/getSysintegrationServerRequest.xml`

### invokeProcess

```
invokeProcess(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ☑️ 已在既有服務驗證 | 未實測 | — |

**用途**：開單。六參數版可同時帶入表單欄位值，四參數版只開單不填值。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 流程 ID |
| `pRequesterId` | string | 申請人員工編號 |
| `pOrgUnitId` | string | 申請人部門 id，由 fetchOrgUnitOfUserId 取得 |
| `pSubject` | string | 單據主旨 |

**回傳**：實測環境已由 bpmbackXmlController.js 驗證可開單成功，回傳值為單號或 OID（本工具未重複開單驗證）。

> 有副作用，會產生真實簽核單。pFormFieldValue 的欄位 id 不會被驗證，錯的欄位照收 —— 送出前務必用 getFormFieldTemplate 對過。

### invokeProcess（多載：6 參數）

```
invokeProcess(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pFormDefOID, string pFormFieldValue, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ☑️ 已在既有服務驗證 | 未實測 | — |

**用途**：開單。六參數版可同時帶入表單欄位值，四參數版只開單不填值。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 流程 ID |
| `pRequesterId` | string | 申請人員工編號 |
| `pOrgUnitId` | string | 申請人部門 id，由 fetchOrgUnitOfUserId 取得 |
| `pFormDefOID` | string | 表單定義 OID，由 findFormOIDsOfProcess 取得 |
| `pFormFieldValue` | string | 表單欄位值 XML 字串，格式見手冊 |
| `pSubject` | string | 單據主旨 |

**回傳**：實測環境已由 bpmbackXmlController.js 驗證可開單成功，回傳值為單號或 OID（本工具未重複開單驗證）。

> 有副作用，會產生真實簽核單。pFormFieldValue 的欄位 id 不會被驗證，錯的欄位照收 —— 送出前務必用 getFormFieldTemplate 對過。

### invokeProcessByOrg

```
invokeProcessByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 未實測 | — |

**用途**：推測為指定公司別開單，與 invokeProcess 的差別在組織參數。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 未確認 |
| `pRequesterId` | string | 未確認 |
| `pOrgUnitId` | string | 未確認 |
| `pOrgId` | string | 未確認 |
| `pSubject` | string | 未確認 |

**回傳**：未驗證。

### invokeProcessByOrg（多載：7 參數）

```
invokeProcessByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pFormDefOID, string pFormFieldValue, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 未實測 | — |

**用途**：推測為指定公司別開單，與 invokeProcess 的差別在組織參數。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 未確認 |
| `pRequesterId` | string | 未確認 |
| `pOrgUnitId` | string | 未確認 |
| `pOrgId` | string | 未確認 |
| `pFormDefOID` | string | 未確認 |
| `pFormFieldValue` | string | 未確認 |
| `pSubject` | string | 未確認 |

**回傳**：未驗證。

### isPerformerOfProcessInstance

```
isPerformerOfProcessInstance(string pUserId, string pProcessInstanceSerialNo) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 39 ms |

**用途**：判斷某人是否為該單的簽核者之一。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pProcessInstanceSerialNo` | string | 單號 |

**回傳**：WSDL 宣告 string，實測回 "1"。回 "0" 的情境未驗證。

回傳樣本：`out/payloads/isPerformerOfProcessInstanceRequest.xml`

---

## 尚未分析的方法

以下 26 支只有介面契約，沒有經過驗證的用途說明。
多數是有副作用的方法（開單、簽核、轉派、作廢），需要可拋棄的測試單才能驗。

| 方法 | 參數 | 回傳 | 未實測原因 |
|:---|:---|:---|:---|
| `acceptWorkItem` | `pWorkItemOID`, `pUserId` | `void` | 有副作用，未經指名不自動呼叫 |
| `addCloneSerialActivity` | `pProcessInstanceSN`, `pActId`, `pRefActId` | `string` | 有副作用，未經指名不自動呼叫 |
| `addCustomActivity` | `pWorkItmeOID`, `pPostActDefsAsXML` | `void` | 有副作用，未經指名不自動呼叫 |
| `addCustomParallelActivity` | `pWorkItmeOID`, `pPostParallelActDefsAsXML` | `void` | 有副作用，未經指名不自動呼叫 |
| `addCustomParallelAndSerialActivity` | `pProcessInstanceSN`, `pActId`, `pRefActId`, `pPostPSActDefsAsXML` | `void` | 有副作用，未經指名不自動呼叫 |
| `addCustomParallelAndSerialActivity` | `pWorkItmeOID`, `pPostPSActDefsAsXML` | `void` | 有副作用，未經指名不自動呼叫 |
| `addLabelToNoticeWorkItem` | `pWorkItemOID`, `pUserOID`, `pLabelOID` | `boolean` | 有副作用，未經指名不自動呼叫 |
| `addUserAbsence` | `pUserId`, `pStartTime`, `pEndTime` | `void` | 有副作用，未經指名不自動呼叫 |
| `assignRelevantDataBySerialNo` | `pProcessInstanceSerialNo`, `pRelevantDataId`, `pRelevantDataValue` | `void` | 有副作用，未經指名不自動呼叫 |
| `assigneeReassignWorkItem` | `pRequesterOID`, `pAcceptorOID`, `pWorkItemOID`, `pReassignComment` | `void` | 有副作用，未經指名不自動呼叫 |
| `bypassActivity` | `pActivityInstanceOID` | `void` | 有副作用，未經指名不自動呼叫 |
| `importOrganizationData` | `pXMLData` | `string` | 有副作用，未經指名不自動呼叫 |
| `increaseViewTimesOfWorkAssignment` | `pUserId`, `pWorkItemOID` | `void` | 有副作用，未經指名不自動呼叫 |
| `invokeProcessAndAddCustAct` | `pProcessPackageId`, `pRequesterId`, `pOrgUnitId`, `pFormDefOID`, `pFormFieldValue`, `pSubject`, `pPostPSActDefsAsXML` | `string` | 有副作用，未經指名不自動呼叫 |
| `invokeProcessAndAddCustActByOrg` | `pProcessPackageId`, `pRequesterId`, `pOrgUnitId`, `pOrgId`, `pFormDefOID`, `pFormFieldValue`, `pSubject`, `pPostPSActDefsAsXML` | `string` | 有副作用，未經指名不自動呼叫 |
| `invokeProcessByParameter` | `pProcessPackageId`, `pRequesterId`, `pOrgUnitId`, `pParameterId`, `pInvokeParameter`, `pSubject` | `string` | 有副作用，未經指名不自動呼叫 |
| `invokeProcessByParameterByOrg` | `pProcessPackageId`, `pRequesterId`, `pOrgUnitId`, `pOrgId`, `pParameterId`, `pInvokeParameter`, `pSubject` | `string` | 有副作用，未經指名不自動呼叫 |
| `managementChangeWorkItemOwner` | `pAcceptorOID`, `pWorkItemOID`, `pReassignComment` | `void` | 有副作用，未經指名不自動呼叫 |
| `managementReassignWorkItem` | `pAcceptorOID`, `pWorkItemOID`, `pReassignComment` | `void` | 有副作用，未經指名不自動呼叫 |
| `reexecuteActivity` | `pProcessSerialNo`, `pAskReexecuteUserId`, `pReexecuteActivityId`, `pReexecuteComment` | `void` | 有副作用，未經指名不自動呼叫 |
| `removeAbsenceRecord` | `pUserId`, `pStartDateTime`, `pEndDateTime` | `void` | 有副作用，未經指名不自動呼叫 |
| `removeLabelFromNoticeWorkItem` | `pWorkItemOID`, `pUserOID`, `pLabelOID` | `boolean` | 有副作用，未經指名不自動呼叫 |
| `reserveNoCmDocument` | `pOriginalFullFileName` | `string` | 有副作用，未經指名不自動呼叫 |
| `terminatedProcessForSerialNo` | `pProcessInstanceSerialNo`, `pUserId`, `pTerminatedComment` | `void` | 有副作用，未經指名不自動呼叫 |
| `updateDefaultSubstitute` | `pUserId`, `pDefaultSubstitutesId` | `void` | 有副作用，未經指名不自動呼叫 |
| `updateFormValueBySerialNember` | `serialNumber`, `pFormValue` | `void` | 有副作用，未經指名不自動呼叫 |
