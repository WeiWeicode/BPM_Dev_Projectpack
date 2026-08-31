# -*- coding: utf-8 -*-
"""改單工作台端點：查流程 → 查單 → 讀欄位 → 預覽 → 寫回。

寫入只有 /api/form-edit/submit 一支，且必須帶 confirm=true。
預覽（preview）純唯讀，可以隨便按。
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from .. import form_edit
from ..schemas import (
    FormEditPreviewRequest,
    FormEditPreviewResult,
    FormEditSubmitRequest,
    FormEditSubmitResult,
    InstanceDetail,
    InstanceListResult,
    ProcessListResult,
)

router = APIRouter(prefix='/api/form-edit', tags=['form-edit'])


def _guard(func, *args, **kwargs):
    """把預期內的錯誤轉成 400，其餘照常往上拋（不吞例外）。"""
    try:
        return func(*args, **kwargs)
    except form_edit.FormEditError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get('/processes', response_model=ProcessListResult)
def list_processes(
    keyword: Optional[str] = Query(None, description='搜尋流程 id、流程名稱或表單名稱'),
    limit: int = Query(200, ge=1, le=1000),
):
    """流程清單。來源為 3_db_explorer 的 form_process_map.json。"""
    return _guard(form_edit.list_processes, keyword or '', limit)


@router.get('/instances', response_model=InstanceListResult)
def list_instances(
    processId: str = Query(..., description='流程 id'),
    scope: str = Query('all', pattern='^(all|running|closed)$'),
    startTime: Optional[str] = Query(None, description='yyyy/MM/dd HH:mm:ss'),
    endTime: Optional[str] = Query(None, description='yyyy/MM/dd HH:mm:ss'),
    dateBasis: str = Query('created', pattern='^(created|closed)$'),
    endpoint: Optional[str] = Query(None),
):
    """查某支流程的單，可篩選進行中或已結案。"""
    return _guard(form_edit.list_instances, processId, scope,
                  startTime, endTime, dateBasis, endpoint)


@router.get('/instance/{serialNo}', response_model=InstanceDetail)
def load_instance(serialNo: str, endpoint: Optional[str] = Query(None)):
    """載入單頭與可編輯的欄位表（含欄位中文名稱，取不到會註明原因）。"""
    return _guard(form_edit.load_instance, serialNo, endpoint)


@router.post('/preview', response_model=FormEditPreviewResult)
def preview(req: FormEditPreviewRequest):
    """預覽將送出的 pFormValue 與逐欄差異。唯讀，不寫入。"""
    return _guard(form_edit.preview_changes, req.serialNo, req.changes, req.endpoint)


@router.post('/submit', response_model=FormEditSubmitResult)
def submit(req: FormEditSubmitRequest):
    """寫回表單值並讀回驗證。必須 confirm=true。"""
    return _guard(form_edit.submit_changes, req.serialNo, req.changes,
                  req.rawFormXml, req.confirm, req.endpoint)
