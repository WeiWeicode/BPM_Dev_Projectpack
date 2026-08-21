# -*- coding: utf-8 -*-
"""流程：清單、關卡明細、權限矩陣。"""

from fastapi import APIRouter, HTTPException, Query, Response

from .. import service
from ..models import Matrix, ProcessDetail, ProcessSummary

router = APIRouter(prefix='/api/processes', tags=['processes'])


@router.get('', response_model=list[ProcessSummary])
def list_processes(response: Response, keyword: str = '',
                   limit: int = Query(None, ge=1, le=1000), offset: int = 0):
    items, total = service.list_processes(keyword, limit, offset)
    response.headers['X-Total-Count'] = str(total)
    return items


@router.get('/{process_id}', response_model=ProcessDetail)
def get_process(process_id: str):
    detail = service.get_process(process_id)
    if detail is None:
        raise HTTPException(404, '找不到已發佈的流程：%s' % process_id)
    return detail


@router.get('/{process_id}/matrix', response_model=Matrix)
def get_matrix(process_id: str, only: str = Query('all', pattern='^(all|button|field)$')):
    matrix = service.get_matrix(process_id, only)
    if matrix is None:
        raise HTTPException(404, '找不到已發佈的流程：%s' % process_id)
    return matrix
