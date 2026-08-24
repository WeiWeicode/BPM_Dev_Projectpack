# 鼎新 BPM WorkflowService API 手冊

| 項目 | 值 |
|:---|:---|
| Endpoint | `http://10.10.130.191:8080/NaNaWeb/services/WorkflowService` |
| 方法總數 | 65 |
| 已寫下語意 | 65 |
| 實測成功 | 60 |
| 實測時間 | 2026-08-24T10:14:21 |

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
| `abortProcessForSerialNo` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `acceptWorkItem` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `addCloneSerialActivity` | ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） |
| `addCustomActivity` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `addCustomParallelActivity` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `addCustomParallelAndSerialActivity` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `addCustomParallelAndSerialActivity` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `addLabelToNoticeWorkItem` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `addUserAbsence` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `assignRelevantDataBySerialNo` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `assigneeReassignWorkItem` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `bypassActivity` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `checkWorkItemState` | ✅ 已實測 | 實測成功 |
| `completeWorkItem` | ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） |
| `countWorkingDays` | ✅ 已實測 | 實測成功 |
| `countWorkingTime` | ✅ 已實測 | 實測成功 |
| `fetchCanTraceProcSN` | ✅ 已實測 | 實測成功 |
| `fetchClosedProcInstances` | ✅ 已實測 | 實測成功 |
| `fetchDefaultSubstituteInfo` | ✅ 已實測 | 實測成功 |
| `fetchDefaultSubstituteInfo` | ✅ 已實測 | 實測成功 |
| `fetchDueDate` | ✅ 已實測 | 實測成功 |
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
| `findManagerByAppLvl` | ✅ 已實測 | 實測成功 |
| `getFormFieldTemplate` | ✅ 已實測 | 實測成功 |
| `getProcessPackage` | ✅ 已實測 | 實測成功 |
| `getProjectsWithOrganizationId` | ✅ 已實測 | 實測成功 |
| `getSubstituteState` | ✅ 已實測 | 實測成功 |
| `getSysintegrationServer` | ✅ 已實測 | 實測成功 |
| `importOrganizationData` | ⚠️ 未實測，僅推測 | 刻意未執行 |
| `increaseViewTimesOfWorkAssignment` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `invokeProcess` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `invokeProcess` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `invokeProcessAndAddCustAct` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `invokeProcessAndAddCustActByOrg` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `invokeProcessByOrg` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `invokeProcessByOrg` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `invokeProcessByParameter` | ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） |
| `invokeProcessByParameterByOrg` | ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） |
| `isPerformerOfProcessInstance` | ✅ 已實測 | 實測成功 |
| `managementChangeWorkItemOwner` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `managementReassignWorkItem` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `reexecuteActivity` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `removeAbsenceRecord` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `removeLabelFromNoticeWorkItem` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `reserveNoCmDocument` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `terminatedProcessForSerialNo` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `updateDefaultSubstitute` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |
| `updateFormValueBySerialNember` | ✅ 已實測（有副作用，實際執行過） | 實測成功 |

---

## 已分析的方法

### abortProcessForSerialNo

```
abortProcessForSerialNo(string pProcessInstanceSerialNo, string pAbortComment) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：作廢流程單。與終止的差別在 state（closed.aborted vs closed.terminated）。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 單號 |
| `pAbortComment` | string | 作廢原因 |

**回傳**：void。

> 不需要傳操作者，比 terminatedProcessForSerialNo 少一個參數。實測用它清理了 20 餘張測試單。

### acceptWorkItem

```
acceptWorkItem(string pWorkItemOID, string pUserId) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：簽收待辦。**簽核前必須先簽收**，否則 completeWorkItem 會回 "The workitem is not running state"。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItemOID` | string | 由 fetchToDoWorkItem 取得 |
| `pUserId` | string | 必須是該待辦目前的擁有者，傳別人會被拒絕 |

**回傳**：void。

> 實測先 accept 再 complete 是必要順序，這在 WSDL 上完全看不出來。

### addCloneSerialActivity

```
addCloneSerialActivity(string pProcessInstanceSN, string pActId, string pRefActId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） | — |

**用途**：複製既有關卡並插入流程。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSN` | string | 單號 |
| `pActId` | string | 關卡 id |
| `pRefActId` | string | 參考關卡 id |

**回傳**：string。**未取得成功樣本。**

> 把 pActId 與 pRefActId 都指向目前關卡時回 ARJUNA016053 交易無法提交。推測兩者不能相同，或被複製的關卡必須處於特定狀態。未進一步確認。

實測錯誤：``

### addCustomActivity

```
addCustomActivity(string pWorkItmeOID, string pPostActDefsAsXML) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：在待辦之後追加自訂串簽關卡。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItmeOID` | string | 工作項目 OID（原廠把 WorkItem 拼成 WorkItme） |
| `pPostActDefsAsXML` | string | **java.util.List 的 XStream 序列化**，空清單寫 <list/> |

**回傳**：void。

> 參數格式是靠錯誤訊息反推出來的：送 <invalid/> 回 CannotResolveClassException，送 ActivityDefinition 類別回 "cannot be cast to java.util.List"，送 <list/> 才通過。**清單元素的類別名仍未確認**，因此只驗證了「空清單」這條路徑，實際加關卡還需要知道元素類別。

### addCustomParallelActivity

```
addCustomParallelActivity(string pWorkItmeOID, string pPostParallelActDefsAsXML) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：追加自訂並簽關卡。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItmeOID` | string | 未確認 |
| `pPostParallelActDefsAsXML` | string | 同上，java.util.List 的 XStream 序列化 |

**回傳**：void。

> 同 addCustomActivity，只驗證過空清單。

### addCustomParallelAndSerialActivity

```
addCustomParallelAndSerialActivity(string pProcessInstanceSN, string pActId, string pRefActId, string pPostPSActDefsAsXML) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：追加並簽 + 串簽混合關卡。兩參數版指定工作項目，四參數版指定單號與關卡。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSN` | string | 單號（四參數版） |
| `pActId` | string | 關卡 id |
| `pRefActId` | string | 參考關卡 id |
| `pPostPSActDefsAsXML` | string | java.util.List 的 XStream 序列化 |

**回傳**：void。

> 兩個多載都以空清單實測通過。

### addCustomParallelAndSerialActivity（多載：2 參數）

```
addCustomParallelAndSerialActivity(string pWorkItmeOID, string pPostPSActDefsAsXML) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：追加並簽 + 串簽混合關卡。兩參數版指定工作項目，四參數版指定單號與關卡。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItmeOID` | string | 未確認 |
| `pPostPSActDefsAsXML` | string | java.util.List 的 XStream 序列化 |

**回傳**：void。

> 兩個多載都以空清單實測通過。

### addLabelToNoticeWorkItem

```
addLabelToNoticeWorkItem(string pWorkItemOID, string pUserOID, string pLabelOID) : boolean
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：為知會項目加標籤。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItemOID` | string | 工作項目 OID |
| `pUserOID` | string | **Users.OID**，不是 Employee.OID |
| `pLabelOID` | string | Labels.OID。測試區只有一個標籤 SEALED（封存） |

**回傳**：boolean。

> 對一般待辦實測**恆回 false**（呼叫成功但沒作用）。方法名的 Notice 是關鍵：對象要是知會項目而非待辦。回 false 不會拋例外，呼叫端要自己判斷。

### addUserAbsence

```
addUserAbsence(string pUserId, string pStartTime, string pEndTime) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：新增請假（不在辦公室）記錄。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pStartTime` | string | 起始時間 |
| `pEndTime` | string | 結束時間 |

**回傳**：void。

> 實測新增後以 getSubstituteState 讀回，isAbsence 由 N 變 Y，驗證通過。

### assignRelevantDataBySerialNo

```
assignRelevantDataBySerialNo(string pProcessInstanceSerialNo, string pRelevantDataId, string pRelevantDataValue) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：設定流程變數（RelevantData）的執行期值。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 單號 |
| `pRelevantDataId` | string | 變數 id，來源見 fetchProcessContextVariable |
| `pRelevantDataValue` | string | 值 |

**回傳**：void。

> 實測寫入後以 fetchProcessContextVariable 讀回確認為新值，來回驗證通過。

### assigneeReassignWorkItem

```
assigneeReassignWorkItem(string pRequesterOID, string pAcceptorOID, string pWorkItemOID, string pReassignComment) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：簽核者自行把待辦轉派給他人。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pRequesterOID` | string | **待辦目前擁有者**的 Users.OID。不是原申請人 |
| `pAcceptorOID` | string | 接收者的 Users.OID |
| `pWorkItemOID` | string | 工作項目 OID |
| `pReassignComment` | string | 轉派意見 |

**回傳**：void。

> pRequesterOID 不是待辦目前擁有者時回 "Requester can not reassign this WorkItem."。實測順序：先用 managementReassignWorkItem 把待辦轉到自己名下，才有資格自行轉派。

### bypassActivity

```
bypassActivity(string pActivityInstanceOID) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：讓關卡跳過，不簽直接放行。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pActivityInstanceOID` | string | 關卡實例 OID。查 ParticipantActivityInstance 表，條件 bypassable=1 且 bypassed=0 |

**回傳**：void。

> 這個 OID 沒有任何 API 查得到，只能查資料庫。關卡是否可跳關由流程定義的 bypassable 決定。

### checkWorkItemState

```
checkWorkItemState(string pWorkItemOID) : int
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 106 ms |

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
| ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） | — |

**用途**：簽核完成，推動流程往下一關。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItemOID` | string | 工作項目 OID |
| `pUserId` | string | 簽核者 |
| `pComment` | string | 簽核意見 |

**回傳**：void。**未取得成功樣本。**

> 在測試流程上一律失敗於 GroupOID cannot be found。已追查到根因：SP_DetectionOPProcess 的參與者設定引用群組 SPDetectionOPGroup，但 Groups 表（581 筆）裡沒有這個群組 —— 是測試區的資料缺漏，不是 API 問題。帶不帶公司別都一樣。要驗證這支方法必須換一支群組設定完整的流程。

實測錯誤：``

### countWorkingDays

```
countWorkingDays(string pUserId, string pStartDateTime, string pEndDateTime, string pDateFormat) : int
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 26 ms |

**用途**：依工作行事曆計算區間內的工作日數。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號，必須有掛工作行事曆 |
| `pStartDateTime` | string | 未確認 |
| `pEndDateTime` | string | 未確認 |
| `pDateFormat` | string | Java SimpleDateFormat 語法，例如 yyyy/MM/dd HH:mm:ss |

**回傳**：int。

> 沒掛行事曆時**不拋例外而是回 0** —— 與 countWorkingTime 的行為不一致，呼叫端不能把 0 當成「這段期間沒有工作日」。

回傳樣本：`out/payloads/countWorkingDaysRequest.xml`

### countWorkingTime

```
countWorkingTime(string pUserId, string pStartDateTime, string pEndDateTime, string pDateFormat) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 50 ms |

**用途**：依工作行事曆計算區間內的工作時間。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號，**必須有掛工作行事曆** |
| `pStartDateTime` | string | 未確認 |
| `pEndDateTime` | string | 未確認 |
| `pDateFormat` | string | Java SimpleDateFormat 語法 |

**回傳**：數字字串。實測 S094009 在 2026/08/01～08/24 回 460800（同期間 countWorkingDays 回 15）。單位推測為秒，未確認。

> 使用者沒掛行事曆（Users.referCalendarOID 為 NULL）時拋 NotFoundException。全庫 8080 人中有 1872 人沒掛，呼叫前要有心理準備。

回傳樣本：`out/payloads/countWorkingTimeRequest.xml`

### fetchCanTraceProcSN

```
fetchCanTraceProcSN(string pProcessIds, string pUserId) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 21 ms |

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
| ✅ 已實測 | 實測成功 | 138 ms |

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
| ✅ 已實測 | 實測成功 | 34 ms |

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
| ✅ 已實測 | 實測成功 | 22 ms |

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
| ✅ 已實測 | 實測成功 | 24 ms |

**用途**：依工作行事曆推算到期日。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號，必須有掛工作行事曆 |
| `pBaseDate` | string | 基準日 |
| `pDueDays` | string | 工作天數 |
| `pDateFormat` | string | 日期格式 |

**回傳**：日期字串。實測 2026/08/24 起算 3 個工作天回 2026/08/27 00:00:00。

> 沒掛行事曆時拋 NotFoundException。

回傳樣本：`out/payloads/fetchDueDateRequest.xml`

### fetchFormInstanceWithProcOID

```
fetchFormInstanceWithProcOID(string pProcessInstanceOID) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 74 ms |

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
| ✅ 已實測 | 實測成功 | 90 ms |

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
| ✅ 已實測 | 實測成功 | 83 ms |

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
| ✅ 已實測 | 實測成功 | 90 ms |

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
| ✅ 已實測 | 實測成功 | 88 ms |

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
| ☑️ 已在既有服務驗證 | 實測成功 | 35 ms |

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
| ✅ 已實測 | 實測成功 | 49 ms |

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
| ✅ 已實測 | 實測成功 | 25 ms |

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
| ✅ 已實測 | 實測成功 | 122 ms |

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
| ✅ 已實測 | 實測成功 | 38 ms |

**用途**：查某人目前在指定關卡待簽的單號（方法名的 Currtent 是原廠拼字錯誤）。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessId` | string | 流程 ID |
| `pActId` | string | 關卡 id，取自 fetchFullProcInstance* 的 activityId |
| `pUserId` | string | 員工編號 |

**回傳**：單號字串。實測回單一單號，多筆時的分隔方式未驗證。

### fetchProcessAbortOrTerminateComment

```
fetchProcessAbortOrTerminateComment(string pProcessSerialNo) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 94 ms |

**用途**：取單子被作廢或終止時填的意見。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessSerialNo` | string | 單號 |

**回傳**：純文字意見。實測格式為「意見內容(員工編號-姓名)」，操作者資訊由 BPM 自動附加。

> 單子仍在跑時會拋例外並明講原因，不是回空字串。查詢前應先確認 state 為 closed.terminated。

回傳樣本：`out/payloads/fetchProcessAbortOrTerminateCommentRequest.xml`

### fetchProcessContextVariable

```
fetchProcessContextVariable(string pProcessSerialNo, string pVariableId, boolean pOnlyTextValue) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 98 ms |

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
| ✅ 已實測 | 實測成功 | 111 ms |

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
| ✅ 已實測 | 實測成功 | 22 ms |

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
| ✅ 已實測 | 實測成功 | 81 ms |

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
| ✅ 已實測 | 實測成功 | 83 ms |

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
| ✅ 已實測 | 實測成功 | 76 ms |

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
| ☑️ 已在既有服務驗證 | 實測成功 | 77 ms |

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
| ✅ 已實測 | 實測成功 | 47 ms |

**用途**：依職務層級往上找主管。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pOrgUnitOID` | string | 部門 OID（OrganizationUnit.OID），由 fetchOrgUnitOfUserId 取得 |
| `pLevelName` | string | **FunctionLevel.functionLevelName**（職務層級，例如「副總經理級」）。不是 OrganizationUnitLevel 的組織層級名稱 |
| `pApprovalLevelType` | string | 實測傳 0、1、DEFAULT、空字串，錯誤訊息一律顯示 Type:null，看不出這個參數有被使用 |
| `pIsDeptManager` | boolean | boolean |

**回傳**：<com.dsc.nana.user_interface.web.webservice.WorkflowService> 內含 userOID / userId / userEmail。

> **這支會把例外包在回傳字串裡**：層級名稱查不到時回 HTTP 200 加 <NotFoundException>Can not found ApprovelLevel by Name:...</NotFoundException>（ApprovelLevel 是原廠拼字）。呼叫端只判斷有無丟例外會誤收。「一般人員」這種最低層級查不到主管，也走同一條回傳路徑。

回傳樣本：`out/payloads/findManagerByAppLvlRequest.xml`

### getFormFieldTemplate

```
getFormFieldTemplate(string pFormDefinitionOID) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 70 ms |

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
| ✅ 已實測 | 實測成功 | 146 ms |

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
| ✅ 已實測 | 實測成功 | 49 ms |

**用途**：依公司別查專案清單。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pOrganizationId` | string | **Organization.id**（GIGASOLAR、WHOLEMAX…），不是部門 id |

**回傳**：ProjectCollection > projects > Project。查無專案時 projects 為空元素。

> 實測 GIGASOLAR 有專案、WHOLEMAX 回空清單。公司別清單查資料庫 Organization 表。

回傳樣本：`out/payloads/getProjectsWithOrganizationIdRequest.xml`

### getSubstituteState

```
getSubstituteState(string pUserId, string pCheckTime) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 21 ms |

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
| ✅ 已實測 | 實測成功 | 15 ms |

**用途**：取系統整合伺服器設定。

**回傳**：實測為字串 "[]"（空清單）。

> 測試區沒有設定整合伺服器，因此看不出非空時的結構。

回傳樣本：`out/payloads/getSysintegrationServerRequest.xml`

### importOrganizationData

```
importOrganizationData(string pXMLData) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 刻意未執行 | — |

**用途**：匯入組織資料。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pXMLData` | string | 組織資料 XML，格式未知 |

**回傳**：string。**刻意未執行。**

> 本專案唯一刻意不實測的方法。組織是所有流程的根基，匯入內容不完整就等同刪除既有部門，與「不刪測試區資料」的約定牴觸。要驗證請在獨立環境進行。

### increaseViewTimesOfWorkAssignment

```
increaseViewTimesOfWorkAssignment(string pUserId, string pWorkItemOID) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：累加待辦的檢視次數。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pWorkItemOID` | string | 工作項目 OID |

**回傳**：void。

### invokeProcess

```
invokeProcess(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：開單。四參數版只開單，六參數版同時帶入表單欄位值。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 流程 ID |
| `pRequesterId` | string | 申請人員工編號 |
| `pOrgUnitId` | string | 申請人部門 id（OrganizationUnit.id，例如 S1800） |
| `pSubject` | string | 單據主旨。實測發現最終主旨由流程的主旨範本決定，這裡送的值不一定會出現 |

**回傳**：新單號字串（例如 SP_DetectionOPProcess00000056），非 XML。

> **四參數版（不帶表單）實測開單失敗**，回 EJBTransactionRolledbackException；六參數版成功。研判此流程的表單有必要欄位，不帶表單值就過不了。開單失敗仍會消耗單號（實測 31、37、39、44 等號碼被吃掉且無對應單據）。欄位 id 不會被驗證，錯的欄位靜默寫入，務必先用 getFormFieldTemplate 對過。

### invokeProcess（多載：6 參數）

```
invokeProcess(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pFormDefOID, string pFormFieldValue, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：開單。四參數版只開單，六參數版同時帶入表單欄位值。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 流程 ID |
| `pRequesterId` | string | 申請人員工編號 |
| `pOrgUnitId` | string | 申請人部門 id（OrganizationUnit.id，例如 S1800） |
| `pFormDefOID` | string | 表單定義 OID，由 findFormOIDsOfProcess 取得 |
| `pFormFieldValue` | string | 表單欄位值 XML，格式見手冊「呼叫前必讀」 |
| `pSubject` | string | 單據主旨。實測發現最終主旨由流程的主旨範本決定，這裡送的值不一定會出現 |

**回傳**：新單號字串（例如 SP_DetectionOPProcess00000056），非 XML。

> **四參數版（不帶表單）實測開單失敗**，回 EJBTransactionRolledbackException；六參數版成功。研判此流程的表單有必要欄位，不帶表單值就過不了。開單失敗仍會消耗單號（實測 31、37、39、44 等號碼被吃掉且無對應單據）。欄位 id 不會被驗證，錯的欄位靜默寫入，務必先用 getFormFieldTemplate 對過。

### invokeProcessAndAddCustAct

```
invokeProcessAndAddCustAct(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pFormDefOID, string pFormFieldValue, string pSubject, string pPostPSActDefsAsXML) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：開單的同時追加自訂關卡。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 未確認 |
| `pRequesterId` | string | 未確認 |
| `pOrgUnitId` | string | 未確認 |
| `pFormDefOID` | string | 未確認 |
| `pFormFieldValue` | string | 未確認 |
| `pSubject` | string | 未確認 |
| `pPostPSActDefsAsXML` | string | java.util.List 的 XStream 序列化。空清單寫 <list/>，實測被接受 |

**回傳**：新單號字串。

> 送 <list/>（空清單）時等同一般開單。清單元素的類別名尚未確認，見 addCustomActivity 的備註。

### invokeProcessAndAddCustActByOrg

```
invokeProcessAndAddCustActByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pFormDefOID, string pFormFieldValue, string pSubject, string pPostPSActDefsAsXML) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：同上，多指定公司別。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 未確認 |
| `pRequesterId` | string | 未確認 |
| `pOrgUnitId` | string | 未確認 |
| `pOrgId` | string | Organization.id |
| `pFormDefOID` | string | 未確認 |
| `pFormFieldValue` | string | 未確認 |
| `pSubject` | string | 未確認 |
| `pPostPSActDefsAsXML` | string | 未確認 |

**回傳**：新單號字串。

### invokeProcessByOrg

```
invokeProcessByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：同 invokeProcess，多一個公司別參數。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 未確認 |
| `pRequesterId` | string | 未確認 |
| `pOrgUnitId` | string | 未確認 |
| `pOrgId` | string | **Organization.id**（例如 GIGASOLAR），不是部門 id |
| `pSubject` | string | 未確認 |

**回傳**：新單號字串。

> 七參數版（帶表單）成功、五參數版（不帶表單）同樣 rollback，與 invokeProcess 一致。實測比較過：帶不帶 pOrgId 對後續簽核的群組解析沒有影響。

### invokeProcessByOrg（多載：7 參數）

```
invokeProcessByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pFormDefOID, string pFormFieldValue, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：同 invokeProcess，多一個公司別參數。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 未確認 |
| `pRequesterId` | string | 未確認 |
| `pOrgUnitId` | string | 未確認 |
| `pOrgId` | string | **Organization.id**（例如 GIGASOLAR），不是部門 id |
| `pFormDefOID` | string | 未確認 |
| `pFormFieldValue` | string | 未確認 |
| `pSubject` | string | 未確認 |

**回傳**：新單號字串。

> 七參數版（帶表單）成功、五參數版（不帶表單）同樣 rollback，與 invokeProcess 一致。實測比較過：帶不帶 pOrgId 對後續簽核的群組解析沒有影響。

### invokeProcessByParameter

```
invokeProcessByParameter(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pParameterId, string pInvokeParameter, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） | — |

**用途**：以流程參數啟動流程。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 未確認 |
| `pRequesterId` | string | 未確認 |
| `pOrgUnitId` | string | 未確認 |
| `pParameterId` | string | 流程變數（RelevantData）id，非任意字串 |
| `pInvokeParameter` | string | 對應的值 |
| `pSubject` | string | 未確認 |

**回傳**：string。**未取得成功樣本。**

> 兩段錯誤訊息把限制講清楚了：亂填 id 回「ProcessDefinition error. If first activity is requester, please set variable as RelevantData.」，改用真實變數 id（isSeparateByVerNo）則 rollback。研判此流程的第一關是申請人、未設定成可用參數啟動，要換流程才驗得出來。

實測錯誤：``

### invokeProcessByParameterByOrg

```
invokeProcessByParameterByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pParameterId, string pInvokeParameter, string pSubject) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ⚠️ 未實測，僅推測 | 實測失敗（SOAP Fault） | — |

**用途**：同上，多指定公司別。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessPackageId` | string | 未確認 |
| `pRequesterId` | string | 未確認 |
| `pOrgUnitId` | string | 未確認 |
| `pOrgId` | string | Organization.id |
| `pParameterId` | string | 未確認 |
| `pInvokeParameter` | string | 未確認 |
| `pSubject` | string | 未確認 |

**回傳**：string。未取得成功樣本，錯誤同上。

實測錯誤：``

### isPerformerOfProcessInstance

```
isPerformerOfProcessInstance(string pUserId, string pProcessInstanceSerialNo) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測 | 實測成功 | 19 ms |

**用途**：判斷某人是否為該單的簽核者之一。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pProcessInstanceSerialNo` | string | 單號 |

**回傳**：WSDL 宣告 string，實測回 "1"。回 "0" 的情境未驗證。

回傳樣本：`out/payloads/isPerformerOfProcessInstanceRequest.xml`

### managementChangeWorkItemOwner

```
managementChangeWorkItemOwner(string pAcceptorOID, string pWorkItemOID, string pReassignComment) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：管理者變更待辦的擁有者。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pAcceptorOID` | string | 新擁有者的 Users.OID |
| `pWorkItemOID` | string | 工作項目 OID |
| `pReassignComment` | string | 意見 |

**回傳**：void。

> 與 managementReassignWorkItem 參數完全相同，語意差別（轉派 vs 換擁有者）在單筆實測中看不出來，未進一步區分。

### managementReassignWorkItem

```
managementReassignWorkItem(string pAcceptorOID, string pWorkItemOID, string pReassignComment) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：管理者強制轉派待辦，不需要目前擁有者同意。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pAcceptorOID` | string | 接收者的 **Users.OID** |
| `pWorkItemOID` | string | 工作項目 OID |
| `pReassignComment` | string | 轉派意見 |

**回傳**：void。

> 傳 Employee.OID 會回 "Can't find User. By OID = ..."。兩張表的 OID 只差一個字元，極容易混淆。

### reexecuteActivity

```
reexecuteActivity(string pProcessSerialNo, string pAskReexecuteUserId, string pReexecuteActivityId, string pReexecuteComment) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：取回重辦：把已簽核的關卡叫回來重新處理。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessSerialNo` | string | 單號 |
| `pAskReexecuteUserId` | string | 提出取回的人 |
| `pReexecuteActivityId` | string | 要重辦的關卡 id |
| `pReexecuteComment` | string | 取回意見 |

**回傳**：void。

> 取回後的意見可由 fetchProcessAbortOrTerminateComment 讀到，格式為「意見內容(員工編號-姓名)」。

### removeAbsenceRecord

```
removeAbsenceRecord(string pUserId, string pStartDateTime, string pEndDateTime) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：刪除請假記錄。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pStartDateTime` | string | 起始時間（要與新增時相同） |
| `pEndDateTime` | string | 結束時間 |

**回傳**：void。

> 實測可把 addUserAbsence 新增的記錄還原。

### removeLabelFromNoticeWorkItem

```
removeLabelFromNoticeWorkItem(string pWorkItemOID, string pUserOID, string pLabelOID) : boolean
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：移除知會項目的標籤。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pWorkItemOID` | string | 未確認 |
| `pUserOID` | string | Users.OID |
| `pLabelOID` | string | Labels.OID |

**回傳**：boolean。對一般待辦同樣恆回 false。

### reserveNoCmDocument

```
reserveNoCmDocument(string pOriginalFullFileName) : string
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：向文件伺服器預留一個附件位置，取得實體路徑與檔名。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pOriginalFullFileName` | string | 原始檔名 |

**回傳**：ReserveNoCmDocInfo，含 docServerId、filePathToSave、OID、physicalName。

> 上傳附件的前置步驟。實際的檔案上傳不走這個 SOAP 服務。

### terminatedProcessForSerialNo

```
terminatedProcessForSerialNo(string pProcessInstanceSerialNo, string pUserId, string pTerminatedComment) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：終止流程單。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pProcessInstanceSerialNo` | string | 單號 |
| `pUserId` | string | 操作者 |
| `pTerminatedComment` | string | 終止原因 |

**回傳**：void。

> 終止後 state 變 closed.terminated，意見可由 fetchProcessAbortOrTerminateComment 讀回。

### updateDefaultSubstitute

```
updateDefaultSubstitute(string pUserId, string pDefaultSubstitutesId) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：設定預設代理人。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `pUserId` | string | 員工編號 |
| `pDefaultSubstitutesId` | string | 代理人員工編號。多筆的分隔方式未驗證 |

**回傳**：void。

> 呼叫成功，但隨後 fetchDefaultSubstituteInfo 仍回 no default substitute found，**寫入是否真的生效未能確認**。可能需要額外的生效時間設定。

### updateFormValueBySerialNember

```
updateFormValueBySerialNember(string serialNumber, string pFormValue) : void
```

| 信心 | 實測狀態 | 耗時 |
|:---|:---|---:|
| ✅ 已實測（有副作用，實際執行過） | 實測成功 | — |

**用途**：改寫已開單的表單欄位值（方法名的 Nember 是原廠拼字錯誤）。

| 參數 | 型別 | 說明 |
|:---|:---|:---|
| `serialNumber` | string | 單號。注意這支的參數名沒有 p 前綴，與其他方法不同 |
| `pFormValue` | string | 表單欄位值 XML，格式同 pFormFieldValue |

**回傳**：void。

> 實測改寫後以 fetchFormInstanceWithProcSerlNo 讀回確認為新值。同樣不驗證欄位 id。

---

## 尚未分析的方法

（無 —— 65 支方法都已寫下用途與參數語意。）
