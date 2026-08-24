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
