# -*- coding: utf-8 -*-
"""API 詮釋資料、方法清單與種子端點。"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response

from ..schemas import (
    OperationDetail,
    OperationSummary,
    OverviewSummary,
    SeedsData,
)
from ..service import service

router = APIRouter(prefix='/api', tags=['meta'])


@router.get('/overview', response_model=OverviewSummary)
def get_overview():
    """取得 WorkflowService 整體統計概況。"""
    return service.get_overview()


@router.get('/seeds', response_model=SeedsData)
def get_seeds():
    """取得測試用種子參數與來源說明。"""
    return service.get_seeds()


@router.get('/operations', response_model=List[OperationSummary])
def list_operations(
    keyword: Optional[str] = Query(None, description='搜尋方法名、參數或用途'),
    level: Optional[str] = Query(None, description='唯讀或寫入 (read / write / all)'),
    confidence: Optional[str] = Query(None, description='信心水準 (verified / external / guess / none / all)'),
    status: Optional[str] = Query(None, description='實測狀態 (ok / fault / soft_error / error / skipped / all)'),
):
    """查詢方法清單（支援多維度篩選）。"""
    return service.list_operations(
        keyword=keyword,
        level=level,
        confidence=confidence,
        status=status,
    )


@router.get('/operations/{name}', response_model=OperationDetail)
def get_operation(
    name: str,
    input_message: Optional[str] = Query(None, description='多載時指名 inputMessage'),
):
    """取得指定方法的完整規格、參數說明與實測樣本。"""
    detail = service.get_operation_detail(name, input_message)
    if not detail:
        raise HTTPException(status_code=404, detail='找不到方法：%s' % name)
    return detail


@router.get('/payloads/{name}')
def get_payload(name: str):
    """取得實測回傳的原始 XML 樣本檔案內容。"""
    content = service.get_payload(name)
    if content is None:
        raise HTTPException(status_code=404, detail='找不到樣本檔：%s' % name)
    return Response(content=content, media_type='application/xml')
