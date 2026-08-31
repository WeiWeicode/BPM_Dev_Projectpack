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
    backupFormXml: Optional[str] = None
    pFormValue: Optional[str] = None
    fieldCountBefore: Optional[int] = None
    fieldCountAfter: Optional[int] = None
    corruptionCleared: bool = False
    elapsedMs: int = 0
    message: Optional[str] = None
