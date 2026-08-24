# -*- coding: utf-8 -*-
"""Pydantic 資料契約。

前後端唯一的真實來源：前端 TypeScript 型別由此匯出的 openapi.json 產生，不手抄。
本檔是專案中唯一需要型別註記的地方（框架需要）。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HostOption(BaseModel):
    key: str
    label: str
    address: str
    production: bool = False      # 正式區，UI 要顯著標示
    web_base: str = ''            # 深連結用的 BPM 網站位址


class Health(BaseModel):
    ok: bool
    database: str = ''
    connection: str = ''          # 不含密碼
    error: str = ''
    host: str = ''
    host_label: str = ''
    production: bool = False
    hosts: list[HostOption] = []


class UserCandidate(BaseModel):
    """同名或同人多帳號時由使用者挑選，程式不自動決定。"""
    oid: str
    id: str
    user_name: str = ''
    mail_address: str = ''
    left: bool = False            # leaveDate 有值，已離職但仍可查舊單


class TodoItem(BaseModel):
    work_item_oid: str
    work_item_name: str = ''      # 關卡名稱
    work_item_state: int          # 0 或 1 才是待辦，97 為卡住的異常關卡
    abnormal: bool = False        # 見 docs/待辦狀態語意.md 第 4 節
    serial_number: str = ''
    process_instance_name: str = ''
    subject: str = ''
    created_time: Optional[datetime] = None
    process_state: Optional[int] = None
    process_state_label: str = ''
    perform_url: str = ''         # 空字串代表沒有可用連結，不是漏填
    trace_url: str = ''           # 流程追蹤（唯讀檢視），不需要工作項目


class RequestedItem(BaseModel):
    serial_number: str
    process_instance_name: str = ''
    subject: str = ''
    created_time: Optional[datetime] = None
    process_state: Optional[int] = None
    process_state_label: str = ''
    current_activities: list[str] = []    # 目前卡在哪些關卡
    trace_url: str = ''


class HandledItem(BaseModel):
    work_item_oid: str
    work_item_name: str = ''
    serial_number: str = ''
    process_instance_name: str = ''
    subject: str = ''
    completed_time: Optional[datetime] = None
    executive_comment: str = ''
    process_state: Optional[int] = None
    process_state_label: str = ''
    trace_url: str = ''


class TodoList(BaseModel):
    user: UserCandidate
    host: str
    total: int
    abnormal_total: int = 0       # 被排除的異常關卡數，明示而非靜默丟棄
    items: list[TodoItem] = []


class RequestedList(BaseModel):
    user: UserCandidate
    host: str
    total: int
    offset: int = 0
    limit: int = 0
    items: list[RequestedItem] = []


class HandledList(BaseModel):
    user: UserCandidate
    host: str
    total: int
    offset: int = 0
    limit: int = 0
    items: list[HandledItem] = []


class ApprovalStep(BaseModel):
    work_item_name: str = ''
    performer_id: str = ''
    performer_name: str = ''
    created_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    executive_comment: str = ''
    work_item_state: Optional[int] = None


class Attachment(BaseModel):
    oid: str = ''
    file_name: str = ''
    original_file_name: str = ''
    file_type: str = ''
    file_size: str = ''
    creator_name: str = ''
    activity_name: str = ''


class FormFieldValue(BaseModel):
    """單一欄位的值 + 表單定義裡的中文顯示名。"""
    id: str
    name: str = ''        # 查不到就是空字串，前端顯示 id —— 不編造名稱
    type: str = ''
    value: str = ''


class GridBlock(BaseModel):
    id: str
    name: str = ''
    columns: list[str] = []
    rows: list[dict[str, str]] = []


class InstanceDetail(BaseModel):
    pi_serial_number: str = ''
    fi_serial_number: str = ''
    process_instance_name: str = ''
    subject: str = ''
    requester_id: str = ''
    requester_name: str = ''
    created_time: Optional[datetime] = None
    process_state: Optional[int] = None
    process_state_label: str = ''
    form_id: str = ''             # 這張單用的表單定義
    form_name: str = ''
    field_values: list[FormFieldValue] = []
    grid_values: list[GridBlock] = []
    attachments: list[Attachment] = []
    approval_history: list[ApprovalStep] = []
    trace_url: str = ''           # 需帶 user_id 查詢參數才有值（追蹤網址要帶檢視者）
    form_parse_error: str = ''    # XML 解析失敗要說出來，不假裝表單沒欄位
    label_source_error: str = ''  # 中文名取不到的原因；欄位值照樣顯示
