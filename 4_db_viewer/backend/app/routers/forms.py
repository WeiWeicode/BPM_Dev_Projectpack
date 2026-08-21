# -*- coding: utf-8 -*-
"""表單：清單、元件明細、使用情形。"""

from fastapi import APIRouter, HTTPException, Query, Response

from .. import service
from ..models import FormDetail, FormSummary, FormUsage

router = APIRouter(prefix='/api/forms', tags=['forms'])


@router.get('', response_model=list[FormSummary])
def list_forms(response: Response, keyword: str = '',
               limit: int = Query(None, ge=1, le=1000), offset: int = 0,
               host: str = ''):
    items, total = service.list_forms(keyword, limit, offset, host)
    response.headers['X-Total-Count'] = str(total)
    return items


@router.get('/{form_id}', response_model=FormDetail)
def get_form(form_id: str, host: str = ''):
    detail = service.get_form(form_id, host)
    if detail is None:
        raise HTTPException(404, '找不到已發佈的表單：%s' % form_id)
    return detail


@router.get('/{form_id}/usage', response_model=list[FormUsage])
def get_form_usage(form_id: str, host: str = ''):
    usage = service.get_form_usage(form_id, host)
    if usage is None:
        raise HTTPException(404, '找不到已發佈的表單：%s' % form_id)
    return usage
