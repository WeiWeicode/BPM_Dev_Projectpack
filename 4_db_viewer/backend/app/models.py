# -*- coding: utf-8 -*-
"""Pydantic 資料契約。

這是前後端唯一的真實來源：前端的 TypeScript 型別由此匯出的 openapi.json 產生，
不手抄。本檔是專案中唯一需要型別註記的地方（框架需要）。
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# 資料庫實測值（取樣 4000 筆 FormFieldAccessDefinition）
Permission = Literal['ENABLED', 'INVISIBLE', 'FULL_CONTROL']


class Health(BaseModel):
    ok: bool
    database: str = ''
    connection: str = ''          # 不含密碼
    server_version: str = ''
    cache: dict = {}
    error: str = ''
    write_enabled: bool = False   # 寫入旗標是否開啟
    writable_processes: list[str] = []


class FormSummary(BaseModel):
    form_id: str
    form_name: str
    version: int
    created_time: Optional[datetime] = None
    field_count: Optional[int] = None      # 清單階段不解析 XML，故可為空


class FormField(BaseModel):
    id: str
    name: str                              # 配對 Label 的中文名
    type: str                              # TEXTBOX / BUTTON / GRID / ...


class FormDetail(FormSummary):
    fields: list[FormField] = []


class FormUsage(BaseModel):
    """這張表單被哪個流程的哪個關卡使用。"""
    process_id: str
    process_name: str
    version: int
    activity_id: str
    activity_name: str
    permission: Optional[Permission] = None


class ActivityPermission(BaseModel):
    id: str
    name: str = ''                         # 由表單定義 join 進來
    type: str = ''                         # 同上；空字串代表對照不到
    permission: Permission
    orphaned: bool = False                 # 權限有、表單定義沒有


class Activity(BaseModel):
    id: str
    name: str
    bpmn_type: str = ''                    # StartEvent / UserTask / SendTask / ...
    perform_type: str = ''                 # NORMAL / NOTICE
    performers: list[str] = []             # PROCESS_REQUESTER / MANAGER / SYSTEM
    form_id: str = ''
    buttons: list[ActivityPermission] = []
    fields: list[ActivityPermission] = []


class Transition(BaseModel):
    from_id: str = Field(serialization_alias='from', validation_alias='from')
    to_id: str = Field(serialization_alias='to', validation_alias='to')
    has_condition: bool = False

    model_config = {'populate_by_name': True}


class ProcessSummary(BaseModel):
    process_id: str
    process_name: str
    version: int
    flow_type: str = ''
    created_time: Optional[datetime] = None


class ProcessDetail(ProcessSummary):
    activities: list[Activity] = []         # 已依 transitions 拓撲排序
    transitions: list[Transition] = []


class MatrixCell(BaseModel):
    permission: Optional[Permission] = None  # None = 未列出 = 唯讀(Disable)
    orphaned: bool = False
    applicable: bool = True                  # False = 該元件不屬於此關卡的表單


class MatrixRow(BaseModel):
    id: str
    name: str = ''
    type: str = ''
    is_button: bool = False
    cells: list[MatrixCell] = []            # 順序對應 columns


class Matrix(BaseModel):
    process_id: str
    process_name: str
    version: int
    columns: list[Activity] = []            # 只含有設定權限的關卡
    rows: list[MatrixRow] = []


class SearchHit(BaseModel):
    kind: Literal['form', 'form_field', 'process', 'activity']
    id: str
    name: str = ''
    parent_id: str = ''                     # 元件所屬表單／關卡所屬流程
    parent_name: str = ''


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit] = []
    truncated: bool = False


# ---------------------------------------------------------------- 寫入

# DISABLE 不是存進資料庫的值，而是「把該元件從權限字串中移除」，
# BPM 設計師會顯示成「唯讀(Disable)」。INVALIDITY 格式未知，不支援。
WritablePermission = Literal['ENABLED', 'INVISIBLE', 'FULL_CONTROL', 'DISABLE']


class PermissionItem(BaseModel):
    id: str
    permission: WritablePermission


class PermissionRequest(BaseModel):
    items: list[PermissionItem]
    token: str = ''               # apply 必填，來自 preview


class PermissionChange(BaseModel):
    id: str
    name: str = ''
    type: str = ''
    before: str
    after: str
    changed: bool


class PermissionPreview(BaseModel):
    process_id: str
    activity_id: str
    activity_name: str = ''
    form_id: str = ''
    perm_oid: str
    object_version: Optional[int] = None
    changes: list[PermissionChange] = []
    changed_count: int = 0
    token: str


class PermissionApplyResult(BaseModel):
    applied: bool
    reason: str = ''
    backup_id: str = ''
    changes: list[PermissionChange] = []


class BackupEntry(BaseModel):
    backup_id: str
    perm_oid: str
    created_at: str
    size: int


class RestoreResult(BaseModel):
    restored: bool
    backup_id: str
    perm_oid: str
