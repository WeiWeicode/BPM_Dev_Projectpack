# -*- coding: utf-8 -*-
"""API 資料契約。

Pydantic 模型是唯一真實來源，前端型別照這裡寫。
本專案唯讀：POST 只用來傳「查詢條件」這種塞不進 query string 的結構，
不存在任何會改到資料庫的端點。
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HostInfo(BaseModel):
    key: str
    label: str
    address: str
    production: bool


class MetaInfo(BaseModel):
    hosts: List[HostInfo]
    defaultHost: str
    maxExportRows: int
    maxScanRows: int
    fieldSampleRows: int


class ProcessSummary(BaseModel):
    processId: str
    processName: str = ''
    instanceCount: int = 0
    firstCreated: Optional[datetime] = None
    lastCreated: Optional[datetime] = None


class ProcessListResult(BaseModel):
    processes: List[ProcessSummary]
    total: int


class FieldInfo(BaseModel):
    id: str
    name: str
    type: str = ''
    named: bool = False
    source: str = ''


class GridColumn(BaseModel):
    id: str
    name: str
    named: bool = False


class GridInfo(BaseModel):
    id: str
    name: str
    columns: List[GridColumn] = []


class FormMeta(BaseModel):
    formId: str
    formName: str = ''
    version: Optional[int] = None
    missing: bool = False


class LabelCoverage(BaseModel):
    named: int
    total: int


class FieldCatalog(BaseModel):
    processId: str
    forms: List[FormMeta] = []
    fields: List[FieldInfo] = []
    grids: List[GridInfo] = []
    sampled: int = 0
    parseFailures: int = 0
    labelCoverage: LabelCoverage


class FixedFilters(BaseModel):
    """畫面上固定存在的四個查詢欄位，加上狀態。"""
    processSerialNumber: str = ''
    formSerialNumber: str = ''
    requester: str = ''
    subject: str = ''
    states: List[int] = []


class CustomFilter(BaseModel):
    fieldId: str
    value: str = ''


class SearchRequest(BaseModel):
    processId: str
    startDate: str = Field(..., description='YYYY-MM-DD，必填')
    endDate: str = Field(..., description='YYYY-MM-DD，必填，含當天')
    filters: FixedFilters = FixedFilters()
    customFilters: List[CustomFilter] = []
    fieldIds: List[str] = []
    page: int = 1
    pageSize: int = 50


class InstanceRow(BaseModel):
    processSerialNumber: str = ''
    formSerialNumber: str = ''
    processId: str = ''
    processName: str = ''
    formId: str = ''
    subject: str = ''
    state: Optional[int] = None
    stateName: str = ''
    createdTime: Optional[datetime] = None
    requesterId: str = ''
    requesterName: str = ''
    orgUnitId: str = ''
    orgUnitName: str = ''
    abortComment: str = ''
    abortedBy: str = ''
    parseError: str = ''
    values: Dict[str, str] = {}


class SearchResult(BaseModel):
    rows: List[InstanceRow]
    total: int
    scanned: int
    truncated: bool
    exact: bool = True
    note: str = ''


class WorkItemRow(BaseModel):
    workItemName: str = ''
    state: Optional[int] = None
    stateName: str = ''
    createdTime: Optional[datetime] = None
    completedTime: Optional[datetime] = None
    performerId: str = ''
    performerName: str = ''
    comment: str = ''


class InstanceDetail(BaseModel):
    summary: InstanceRow
    formId: str = ''
    fields: List[FieldInfo] = []
    values: Dict[str, str] = {}
    grids: Dict[str, List[Dict[str, str]]] = {}
    workItems: List[WorkItemRow] = []
    parseError: str = ''


class ExportRequest(BaseModel):
    processId: str
    startDate: str
    endDate: str
    filters: FixedFilters = FixedFilters()
    customFilters: List[CustomFilter] = []
    fieldIds: List[str] = []
    gridIds: List[str] = []
    exportList: bool = True
    exportContent: bool = False
    exportSignatures: bool = False


class ExportPreview(BaseModel):
    matched: int
    limit: int
    exceeded: bool
    exact: bool
    note: str = ''
