# WorkflowServiceService API 清單

> 由 `wsdl_dump.py` 自 WSDL 擷取，只記錄介面契約，未分析用途。

| 項目 | 值 |
|:---|:---|
| WSDL | `http://10.10.130.191:8080/NaNaWeb/services/WorkflowService?wsdl` |
| Endpoint | `http://10.10.130.191:8080/NaNaWeb/services/WorkflowService` |
| targetNamespace | `http://webservice.nana.dsc.com/` |
| SOAP 風格 | `rpc` / `encoded` |
| 方法數 | 65 |
| 擷取時間 | 2026-08-24T08:55:54 |

## 方法一覽

| # | 方法 | 參數（依 parameterOrder） | 回傳 |
|---:|:---|:---|:---|
| 1 | `abortProcessForSerialNo` | `pProcessInstanceSerialNo` string<br>`pAbortComment` string | `void` |
| 2 | `acceptWorkItem` | `pWorkItemOID` string<br>`pUserId` string | `void` |
| 3 | `addCloneSerialActivity` | `pProcessInstanceSN` string<br>`pActId` string<br>`pRefActId` string | `string` |
| 4 | `addCustomActivity` | `pWorkItmeOID` string<br>`pPostActDefsAsXML` string | `void` |
| 5 | `addCustomParallelActivity` | `pWorkItmeOID` string<br>`pPostParallelActDefsAsXML` string | `void` |
| 6 | `addCustomParallelAndSerialActivity` | `pProcessInstanceSN` string<br>`pActId` string<br>`pRefActId` string<br>`pPostPSActDefsAsXML` string | `void` |
| 7 | `addCustomParallelAndSerialActivity` | `pWorkItmeOID` string<br>`pPostPSActDefsAsXML` string | `void` |
| 8 | `addLabelToNoticeWorkItem` | `pWorkItemOID` string<br>`pUserOID` string<br>`pLabelOID` string | `boolean` |
| 9 | `addUserAbsence` | `pUserId` string<br>`pStartTime` string<br>`pEndTime` string | `void` |
| 10 | `assignRelevantDataBySerialNo` | `pProcessInstanceSerialNo` string<br>`pRelevantDataId` string<br>`pRelevantDataValue` string | `void` |
| 11 | `assigneeReassignWorkItem` | `pRequesterOID` string<br>`pAcceptorOID` string<br>`pWorkItemOID` string<br>`pReassignComment` string | `void` |
| 12 | `bypassActivity` | `pActivityInstanceOID` string | `void` |
| 13 | `checkWorkItemState` | `pWorkItemOID` string | `int` |
| 14 | `completeWorkItem` | `pWorkItemOID` string<br>`pUserId` string<br>`pComment` string | `void` |
| 15 | `countWorkingDays` | `pUserId` string<br>`pStartDateTime` string<br>`pEndDateTime` string<br>`pDateFormat` string | `int` |
| 16 | `countWorkingTime` | `pUserId` string<br>`pStartDateTime` string<br>`pEndDateTime` string<br>`pDateFormat` string | `string` |
| 17 | `fetchCanTraceProcSN` | `pProcessIds` string<br>`pUserId` string | `string` |
| 18 | `fetchClosedProcInstances` | `pProcessId` string<br>`pProcessClosedStartTime` string<br>`pProcessClosedEndTime` string<br>`pProcInstanceClosedState` string | `string` |
| 19 | `fetchDefaultSubstituteInfo` | `pUserId` string<br>`pStartSeq` int<br>`pEndSeq` int<br>`pDate` string | `string` |
| 20 | `fetchDefaultSubstituteInfo` | `pUserId` string<br>`pStartSeq` int<br>`pEndSeq` int | `string` |
| 21 | `fetchDueDate` | `pUserId` string<br>`pBaseDate` string<br>`pDueDays` string<br>`pDateFormat` string | `string` |
| 22 | `fetchFormInstanceWithProcOID` | `pProcessInstanceOID` string | `string` |
| 23 | `fetchFormInstanceWithProcSerlNo` | `pProcessInstanceSerialNo` string | `string` |
| 24 | `fetchFullProcInstanceWithOID` | `pProcessInstanceOID` string | `string` |
| 25 | `fetchFullProcInstanceWithSerialNo` | `pProcessInstanceSerialNo` string | `string` |
| 26 | `fetchFullProcInstanceWithSerialNoShowReferences` | `pProcessInstanceSerialNo` string<br>`pShowReferences` boolean | `string` |
| 27 | `fetchOrgUnitOfUserId` | `pUserId` string | `string` |
| 28 | `fetchProcInstanceWithOID` | `pProcessInstanceOID` string | `string` |
| 29 | `fetchProcInstanceWithSerialNo` | `pProcessInstanceSerialNo` string | `string` |
| 30 | `fetchProcInstances` | `pProcessId` string<br>`pProcessInitialStartTime` string<br>`pProcessInitialEndTime` string<br>`pProcInstanceState` string | `string` |
| 31 | `fetchProcSNMatchCurrtentPerformer` | `pProcessId` string<br>`pActId` string<br>`pUserId` string | `string` |
| 32 | `fetchProcessAbortOrTerminateComment` | `pProcessSerialNo` string | `string` |
| 33 | `fetchProcessContextVariable` | `pProcessSerialNo` string<br>`pVariableId` string<br>`pOnlyTextValue` boolean | `string` |
| 34 | `fetchProcessContextVariable` | `pProcessSerialNo` string<br>`pVariableId` string | `string` |
| 35 | `fetchToDoWorkItem` | `pProcessIds` string<br>`pUserId` string | `string` |
| 36 | `fetchUniFormatFormInstanceWithProcOID` | `pProcessInstanceOID` string | `string` |
| 37 | `fetchUniFormatFormInstanceWithProcSerlNo` | `pProcessInstanceSerialNo` string | `string` |
| 38 | `fetchWorkItemCount` | `pUserID` string<br>`pAccessCondition` int<br>`pViewTimesType` string | `int` |
| 39 | `findFormOIDsOfProcess` | `pProcessPackageId` string | `string` |
| 40 | `findManagerByAppLvl` | `pUserId` string<br>`pOrgUnitOID` string<br>`pLevelName` string<br>`pApprovalLevelType` string<br>`pIsDeptManager` boolean | `string` |
| 41 | `getFormFieldTemplate` | `pFormDefinitionOID` string | `string` |
| 42 | `getProcessPackage` | `pProcessPackageId` string | `string` |
| 43 | `getProjectsWithOrganizationId` | `pOrganizationId` string | `string` |
| 44 | `getSubstituteState` | `pUserId` string<br>`pCheckTime` string | `string` |
| 45 | `getSysintegrationServer` | （無） | `string` |
| 46 | `importOrganizationData` | `pXMLData` string | `string` |
| 47 | `increaseViewTimesOfWorkAssignment` | `pUserId` string<br>`pWorkItemOID` string | `void` |
| 48 | `invokeProcess` | `pProcessPackageId` string<br>`pRequesterId` string<br>`pOrgUnitId` string<br>`pSubject` string | `string` |
| 49 | `invokeProcess` | `pProcessPackageId` string<br>`pRequesterId` string<br>`pOrgUnitId` string<br>`pFormDefOID` string<br>`pFormFieldValue` string<br>`pSubject` string | `string` |
| 50 | `invokeProcessAndAddCustAct` | `pProcessPackageId` string<br>`pRequesterId` string<br>`pOrgUnitId` string<br>`pFormDefOID` string<br>`pFormFieldValue` string<br>`pSubject` string<br>`pPostPSActDefsAsXML` string | `string` |
| 51 | `invokeProcessAndAddCustActByOrg` | `pProcessPackageId` string<br>`pRequesterId` string<br>`pOrgUnitId` string<br>`pOrgId` string<br>`pFormDefOID` string<br>`pFormFieldValue` string<br>`pSubject` string<br>`pPostPSActDefsAsXML` string | `string` |
| 52 | `invokeProcessByOrg` | `pProcessPackageId` string<br>`pRequesterId` string<br>`pOrgUnitId` string<br>`pOrgId` string<br>`pSubject` string | `string` |
| 53 | `invokeProcessByOrg` | `pProcessPackageId` string<br>`pRequesterId` string<br>`pOrgUnitId` string<br>`pOrgId` string<br>`pFormDefOID` string<br>`pFormFieldValue` string<br>`pSubject` string | `string` |
| 54 | `invokeProcessByParameter` | `pProcessPackageId` string<br>`pRequesterId` string<br>`pOrgUnitId` string<br>`pParameterId` string<br>`pInvokeParameter` string<br>`pSubject` string | `string` |
| 55 | `invokeProcessByParameterByOrg` | `pProcessPackageId` string<br>`pRequesterId` string<br>`pOrgUnitId` string<br>`pOrgId` string<br>`pParameterId` string<br>`pInvokeParameter` string<br>`pSubject` string | `string` |
| 56 | `isPerformerOfProcessInstance` | `pUserId` string<br>`pProcessInstanceSerialNo` string | `string` |
| 57 | `managementChangeWorkItemOwner` | `pAcceptorOID` string<br>`pWorkItemOID` string<br>`pReassignComment` string | `void` |
| 58 | `managementReassignWorkItem` | `pAcceptorOID` string<br>`pWorkItemOID` string<br>`pReassignComment` string | `void` |
| 59 | `reexecuteActivity` | `pProcessSerialNo` string<br>`pAskReexecuteUserId` string<br>`pReexecuteActivityId` string<br>`pReexecuteComment` string | `void` |
| 60 | `removeAbsenceRecord` | `pUserId` string<br>`pStartDateTime` string<br>`pEndDateTime` string | `void` |
| 61 | `removeLabelFromNoticeWorkItem` | `pWorkItemOID` string<br>`pUserOID` string<br>`pLabelOID` string | `boolean` |
| 62 | `reserveNoCmDocument` | `pOriginalFullFileName` string | `string` |
| 63 | `terminatedProcessForSerialNo` | `pProcessInstanceSerialNo` string<br>`pUserId` string<br>`pTerminatedComment` string | `void` |
| 64 | `updateDefaultSubstitute` | `pUserId` string<br>`pDefaultSubstitutesId` string | `void` |
| 65 | `updateFormValueBySerialNember` | `serialNumber` string<br>`pFormValue` string | `void` |

## 簽章速查

```
abortProcessForSerialNo(string pProcessInstanceSerialNo, string pAbortComment) : void
acceptWorkItem(string pWorkItemOID, string pUserId) : void
addCloneSerialActivity(string pProcessInstanceSN, string pActId, string pRefActId) : string
addCustomActivity(string pWorkItmeOID, string pPostActDefsAsXML) : void
addCustomParallelActivity(string pWorkItmeOID, string pPostParallelActDefsAsXML) : void
addCustomParallelAndSerialActivity(string pProcessInstanceSN, string pActId, string pRefActId, string pPostPSActDefsAsXML) : void
addCustomParallelAndSerialActivity(string pWorkItmeOID, string pPostPSActDefsAsXML) : void
addLabelToNoticeWorkItem(string pWorkItemOID, string pUserOID, string pLabelOID) : boolean
addUserAbsence(string pUserId, string pStartTime, string pEndTime) : void
assignRelevantDataBySerialNo(string pProcessInstanceSerialNo, string pRelevantDataId, string pRelevantDataValue) : void
assigneeReassignWorkItem(string pRequesterOID, string pAcceptorOID, string pWorkItemOID, string pReassignComment) : void
bypassActivity(string pActivityInstanceOID) : void
checkWorkItemState(string pWorkItemOID) : int
completeWorkItem(string pWorkItemOID, string pUserId, string pComment) : void
countWorkingDays(string pUserId, string pStartDateTime, string pEndDateTime, string pDateFormat) : int
countWorkingTime(string pUserId, string pStartDateTime, string pEndDateTime, string pDateFormat) : string
fetchCanTraceProcSN(string pProcessIds, string pUserId) : string
fetchClosedProcInstances(string pProcessId, string pProcessClosedStartTime, string pProcessClosedEndTime, string pProcInstanceClosedState) : string
fetchDefaultSubstituteInfo(string pUserId, int pStartSeq, int pEndSeq, string pDate) : string
fetchDefaultSubstituteInfo(string pUserId, int pStartSeq, int pEndSeq) : string
fetchDueDate(string pUserId, string pBaseDate, string pDueDays, string pDateFormat) : string
fetchFormInstanceWithProcOID(string pProcessInstanceOID) : string
fetchFormInstanceWithProcSerlNo(string pProcessInstanceSerialNo) : string
fetchFullProcInstanceWithOID(string pProcessInstanceOID) : string
fetchFullProcInstanceWithSerialNo(string pProcessInstanceSerialNo) : string
fetchFullProcInstanceWithSerialNoShowReferences(string pProcessInstanceSerialNo, boolean pShowReferences) : string
fetchOrgUnitOfUserId(string pUserId) : string
fetchProcInstanceWithOID(string pProcessInstanceOID) : string
fetchProcInstanceWithSerialNo(string pProcessInstanceSerialNo) : string
fetchProcInstances(string pProcessId, string pProcessInitialStartTime, string pProcessInitialEndTime, string pProcInstanceState) : string
fetchProcSNMatchCurrtentPerformer(string pProcessId, string pActId, string pUserId) : string
fetchProcessAbortOrTerminateComment(string pProcessSerialNo) : string
fetchProcessContextVariable(string pProcessSerialNo, string pVariableId, boolean pOnlyTextValue) : string
fetchProcessContextVariable(string pProcessSerialNo, string pVariableId) : string
fetchToDoWorkItem(string pProcessIds, string pUserId) : string
fetchUniFormatFormInstanceWithProcOID(string pProcessInstanceOID) : string
fetchUniFormatFormInstanceWithProcSerlNo(string pProcessInstanceSerialNo) : string
fetchWorkItemCount(string pUserID, int pAccessCondition, string pViewTimesType) : int
findFormOIDsOfProcess(string pProcessPackageId) : string
findManagerByAppLvl(string pUserId, string pOrgUnitOID, string pLevelName, string pApprovalLevelType, boolean pIsDeptManager) : string
getFormFieldTemplate(string pFormDefinitionOID) : string
getProcessPackage(string pProcessPackageId) : string
getProjectsWithOrganizationId(string pOrganizationId) : string
getSubstituteState(string pUserId, string pCheckTime) : string
getSysintegrationServer() : string
importOrganizationData(string pXMLData) : string
increaseViewTimesOfWorkAssignment(string pUserId, string pWorkItemOID) : void
invokeProcess(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pSubject) : string
invokeProcess(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pFormDefOID, string pFormFieldValue, string pSubject) : string
invokeProcessAndAddCustAct(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pFormDefOID, string pFormFieldValue, string pSubject, string pPostPSActDefsAsXML) : string
invokeProcessAndAddCustActByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pFormDefOID, string pFormFieldValue, string pSubject, string pPostPSActDefsAsXML) : string
invokeProcessByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pSubject) : string
invokeProcessByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pFormDefOID, string pFormFieldValue, string pSubject) : string
invokeProcessByParameter(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pParameterId, string pInvokeParameter, string pSubject) : string
invokeProcessByParameterByOrg(string pProcessPackageId, string pRequesterId, string pOrgUnitId, string pOrgId, string pParameterId, string pInvokeParameter, string pSubject) : string
isPerformerOfProcessInstance(string pUserId, string pProcessInstanceSerialNo) : string
managementChangeWorkItemOwner(string pAcceptorOID, string pWorkItemOID, string pReassignComment) : void
managementReassignWorkItem(string pAcceptorOID, string pWorkItemOID, string pReassignComment) : void
reexecuteActivity(string pProcessSerialNo, string pAskReexecuteUserId, string pReexecuteActivityId, string pReexecuteComment) : void
removeAbsenceRecord(string pUserId, string pStartDateTime, string pEndDateTime) : void
removeLabelFromNoticeWorkItem(string pWorkItemOID, string pUserOID, string pLabelOID) : boolean
reserveNoCmDocument(string pOriginalFullFileName) : string
terminatedProcessForSerialNo(string pProcessInstanceSerialNo, string pUserId, string pTerminatedComment) : void
updateDefaultSubstitute(string pUserId, string pDefaultSubstitutesId) : void
updateFormValueBySerialNember(string serialNumber, string pFormValue) : void
```
