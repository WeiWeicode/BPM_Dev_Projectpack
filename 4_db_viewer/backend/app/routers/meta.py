# -*- coding: utf-8 -*-
"""連線狀態與全域搜尋。"""

from fastapi import APIRouter, Query

from .. import service
from ..models import Health, SearchResult

router = APIRouter(prefix='/api', tags=['meta'])


@router.get('/health', response_model=Health)
def get_health(host: str = ''):
    return service.health(host)


@router.get('/search', response_model=SearchResult)
def get_search(q: str = Query(min_length=2),
               limit: int = Query(50, ge=1, le=200),
               include_fields: bool = False, host: str = ''):
    """搜尋表單、流程與關卡。

    include_fields 會一併掃表單元件，但首次需要解析所有已發佈表單的 XML，
    相當慢（之後有快取），故預設關閉。
    """
    return service.search(q, limit, include_fields, host)
