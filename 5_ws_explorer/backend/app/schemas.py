# -*- coding: utf-8 -*-
"""Pydantic 資料模型定義。"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParameterInfo(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    defaultValue: Optional[Any] = None


class ReturnInfo(BaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class OperationSummary(BaseModel):
    name: str
    inputMessage: str
    level: str  # read / write
    confidence: str  # verified / external / guess / none
    confidenceLabel: str
    status: str  # ok / fault / error / soft_error / skipped
    statusLabel: str
    elapsedMs: Optional[int] = None
    purpose: Optional[str] = None
    parameterCount: int
    parameters: List[ParameterInfo] = Field(default_factory=list)
    returns: Optional[ReturnInfo] = None
    hasPayload: bool = False


class OperationDetail(BaseModel):
    name: str
    inputMessage: str
    portType: str
    parameterOrder: List[str] = Field(default_factory=list)
    level: str  # read / write
    confidence: str
    confidenceLabel: str
    status: str
    statusLabel: str
    elapsedMs: Optional[int] = None
    purpose: Optional[str] = None
    parameters: List[ParameterInfo] = Field(default_factory=list)
    returns: Optional[ReturnInfo] = None
    remarks: Optional[str] = None
    payloadPath: Optional[str] = None
    payloadSample: Optional[str] = None
    faultCode: Optional[str] = None
    faultString: Optional[str] = None
    error: Optional[str] = None
    softError: Optional[str] = None
    reason: Optional[str] = None
    returnShape: Optional[str] = None
    signature: str


class OverviewSummary(BaseModel):
    endpoint: str
    targetNamespace: str
    operationCount: int
    documentedCount: int
    verifiedCount: int
    probedAt: Optional[str] = None
    statusCounts: Dict[str, int] = Field(default_factory=dict)
    confidenceCounts: Dict[str, int] = Field(default_factory=dict)
    levelCounts: Dict[str, int] = Field(default_factory=dict)


class SeedsData(BaseModel):
    seeds: Dict[str, Any] = Field(default_factory=dict)
    sources: Dict[str, str] = Field(default_factory=dict)
    overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class InvokeRequest(BaseModel):
    operationName: str
    inputMessage: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    allowWrite: bool = False
    endpoint: Optional[str] = None


class InvokeResult(BaseModel):
    status: str  # ok / fault / soft_error / error
    elapsedMs: int
    value: Optional[str] = None
    rawResponse: Optional[str] = None
    requestEnvelope: Optional[str] = None
    returnShape: Optional[str] = None
    faultCode: Optional[str] = None
    faultString: Optional[str] = None
    softError: Optional[str] = None
    error: Optional[str] = None


# ── 改單工作台 ──────────────────────────────────────────────────

class ProcessOption(BaseModel):
    processId: Optional[str] = None
    processName: Optional[str] = None
    version: Optional[int] = None
    formIds: List[str] = Field(default_factory=list)
    formNames: List[str] = Field(default_factory=list)


class ProcessListResult(BaseModel):
    processes: List[ProcessOption] = Field(default_factory=list)
    total: int = 0
    truncated: bool = False
    source: Optional[str] = None


class InstanceSummary(BaseModel):
    serialNo: Optional[str] = None
    oid: Optional[str] = None
    state: Optional[str] = None
    subject: Optional[str] = None
    requesterId: Optional[str] = None
    requesterName: Optional[str] = None
    createdTime: Optional[str] = None
    processId: Optional[str] = None
    processName: Optional[str] = None


class InstanceListResult(BaseModel):
    instances: List[InstanceSummary] = Field(default_factory=list)
    total: int = 0
    method: Optional[str] = None
    elapsedMs: int = 0


class FormFieldInfo(BaseModel):
    tag: str
    id: str
    value: str = ''
    name: Optional[str] = None
    dataType: Optional[str] = None
    fieldType: Optional[str] = None
    attrBacked: bool = False
    attributes: Dict[str, str] = Field(default_factory=dict)
    extraAttributes: Dict[str, str] = Field(default_factory=dict)


class InstanceDetail(BaseModel):
    header: InstanceSummary
    formId: Optional[str] = None
    formIdFromResponse: Optional[str] = None
    formSerialNumber: Optional[str] = None
    fields: List[FormFieldInfo] = Field(default_factory=list)
    rawFormXml: str = ''
    labelSource: Optional[str] = None
    labelsAvailable: bool = False
    corruption: Optional[str] = None
    closed: bool = False
    elapsedMs: int = 0


class FieldDiff(BaseModel):
    tag: str
    before: Optional[str] = None
    after: Optional[str] = None


class FieldMismatch(BaseModel):
    tag: str
    expected: Optional[str] = None
    actual: Optional[str] = None


class FormEditPreviewRequest(BaseModel):
    serialNo: str
    changes: Dict[str, str] = Field(default_factory=dict)
    endpoint: Optional[str] = None


class FormEditPreviewResult(BaseModel):
    serialNo: Optional[str] = None
    diff: List[FieldDiff] = Field(default_factory=list)
    fieldCount: int = 0
    pFormValue: str = ''
    unchanged: bool = False


class FormEditSubmitRequest(BaseModel):
    serialNo: str
    changes: Dict[str, str] = Field(default_factory=dict)
    rawFormXml: Optional[str] = None
    confirm: bool = False
    endpoint: Optional[str] = None


class FormEditSubmitResult(BaseModel):
    status: str  # ok / mismatch / unchanged
    serialNo: Optional[str] = None
    diff: List[FieldDiff] = Field(default_factory=list)
    verified: bool = False
    mismatches: List[FieldMismatch] = Field(default_factory=list)
    systemFilled: List[FieldMismatch] = Field(default_factory=list)
    backupFormXml: Optional[str] = None
    pFormValue: Optional[str] = None
    fieldCountBefore: Optional[int] = None
    fieldCountAfter: Optional[int] = None
    corruptionCleared: bool = False
    elapsedMs: int = 0
    message: Optional[str] = None


class OrgUnitOption(BaseModel):
    oid: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    orgName: Optional[str] = None
    isMain: bool = False


class OrgUnitListResult(BaseModel):
    userId: Optional[str] = None
    orgUnits: List[OrgUnitOption] = Field(default_factory=list)


class NewFormTemplate(BaseModel):
    processId: Optional[str] = None
    formOid: Optional[str] = None
    formId: Optional[str] = None
    fields: List[FormFieldInfo] = Field(default_factory=list)
    rawFormXml: str = ''
    labelSource: Optional[str] = None
    labelsAvailable: bool = False
    elapsedMs: int = 0


class CreateInstanceRequest(BaseModel):
    processId: str
    requesterId: str
    orgUnitId: str
    subject: str = ''
    values: Dict[str, str] = Field(default_factory=dict)
    orgId: Optional[str] = None
    confirm: bool = False
    endpoint: Optional[str] = None


class CreateInstanceResult(BaseModel):
    status: str  # ok / mismatch
    method: Optional[str] = None
    serialNo: Optional[str] = None
    requestedSubject: Optional[str] = None
    actualSubject: Optional[str] = None
    subjectOverridden: bool = False
    formOid: Optional[str] = None
    fieldCount: int = 0
    verified: bool = False
    mismatches: List[FieldMismatch] = Field(default_factory=list)
    systemFilled: List[FieldMismatch] = Field(default_factory=list)
    pFormFieldValue: Optional[str] = None
    elapsedMs: int = 0
    message: Optional[str] = None


# ── 關卡工作台 ──────────────────────────────────────────────────

class ActivityInfo(BaseModel):
    activityId: Optional[str] = None
    activityName: Optional[str] = None
    state: Optional[str] = None
    startedTime: Optional[str] = None
    performType: Optional[str] = None
    performerIds: List[str] = Field(default_factory=list)
    notifiedIds: List[str] = Field(default_factory=list)
    comments: List[str] = Field(default_factory=list)
    running: bool = False


class CurrentPerformer(BaseModel):
    userId: Optional[str] = None
    userName: Optional[str] = None
    usersOid: Optional[str] = None
    activityId: Optional[str] = None
    activityName: Optional[str] = None
    workItemOID: Optional[str] = None
    workItemState: Optional[str] = None
    accepted: Optional[bool] = None


class ActivityBoard(BaseModel):
    serialNo: Optional[str] = None
    processId: Optional[str] = None
    processName: Optional[str] = None
    subject: Optional[str] = None
    processState: Optional[str] = None
    closed: bool = False
    activities: List[ActivityInfo] = Field(default_factory=list)
    currentPerformers: List[CurrentPerformer] = Field(default_factory=list)
    oidSource: Optional[str] = None
    reassignAvailable: bool = False
    elapsedMs: int = 0


class StepResult(BaseModel):
    step: str
    ok: bool
    detail: Optional[str] = None


class AcceptRequest(BaseModel):
    workItemOID: str
    userId: str
    confirm: bool = False
    endpoint: Optional[str] = None


class AcceptResult(BaseModel):
    status: str
    workItemState: Optional[str] = None
    accepted: bool = False
    elapsedMs: int = 0
    message: Optional[str] = None


class CompleteRequest(BaseModel):
    serialNo: str
    workItemOID: str
    userId: str
    comment: str = ''
    changes: Dict[str, str] = Field(default_factory=dict)
    autoAccept: bool = True
    confirm: bool = False
    endpoint: Optional[str] = None


class CompleteResult(BaseModel):
    status: str
    steps: List[StepResult] = Field(default_factory=list)
    formResult: Optional[FormEditSubmitResult] = None
    after: Optional[ActivityBoard] = None
    elapsedMs: int = 0
    message: Optional[str] = None


class ReassignRequest(BaseModel):
    workItemOID: str
    acceptorId: str
    comment: str = ''
    mode: str = 'management'  # management / assignee / owner
    requesterId: str = ''
    confirm: bool = False
    endpoint: Optional[str] = None


class ReassignResult(BaseModel):
    status: str
    method: Optional[str] = None
    acceptorId: Optional[str] = None
    acceptorOid: Optional[str] = None
    elapsedMs: int = 0
    message: Optional[str] = None


class ReexecuteRequest(BaseModel):
    serialNo: str
    askUserId: str
    activityId: str
    comment: str = ''
    confirm: bool = False
    endpoint: Optional[str] = None


class ReexecuteResult(BaseModel):
    status: str
    after: Optional[ActivityBoard] = None
    elapsedMs: int = 0
    message: Optional[str] = None


class CloseProcessRequest(BaseModel):
    serialNo: str
    mode: str = 'abort'  # abort / terminate
    userId: str = ''
    comment: str = ''
    confirm: bool = False
    endpoint: Optional[str] = None


class CloseProcessResult(BaseModel):
    status: str
    method: Optional[str] = None
    processState: Optional[str] = None
    savedComment: Optional[str] = None
    elapsedMs: int = 0
    message: Optional[str] = None
