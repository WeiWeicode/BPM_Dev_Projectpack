# -*- coding: utf-8 -*-
"""流程清單與欄位清單端點。全部唯讀。"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import catalog, db, settings
from ..schemas import FieldCatalog, MetaInfo, ProcessListResult

router = APIRouter(prefix='/api', tags=['catalog'])


@router.get('/meta', response_model=MetaInfo)
def meta():
    """可切換的主機與各項上限。前端靠這支決定下拉選單與提示文字。"""
    return {
        'hosts': db.host_list(),
        'defaultHost': settings.DEFAULT_HOST,
        'maxExportRows': settings.MAX_EXPORT_ROWS,
        'maxScanRows': settings.MAX_SCAN_ROWS,
        'fieldSampleRows': settings.FIELD_SAMPLE_ROWS,
    }


@router.get('/processes', response_model=ProcessListResult)
def list_processes(
    host: Optional[str] = Query(None, description='主機 key，見 /api/meta'),
    keyword: Optional[str] = Query(None, description='比對流程 ID 或流程名稱'),
    limit: int = Query(500, ge=1, le=2000),
):
    """有開過單的流程清單，依單據數由多到少。"""
    try:
        processes, total = catalog.list_processes(host, keyword or '', limit)
    except Exception as err:
        raise HTTPException(status_code=502,
                            detail='查詢流程清單失敗（%s: %s）'
                                   % (type(err).__name__, str(err)[:200]))
    return {'processes': processes, 'total': total}


@router.get('/processes/{process_id}/fields', response_model=FieldCatalog)
def process_fields(process_id: str, host: Optional[str] = Query(None)):
    """這支流程可查詢／可匯出的欄位。

    名稱查不到的欄位 named 會是 false，前端要據此標示「只有欄位 ID」，
    不要在畫面上把 ID 當成名稱呈現。
    """
    try:
        return catalog.field_catalog(host, process_id)
    except Exception as err:
        raise HTTPException(status_code=502,
                            detail='取欄位清單失敗（%s: %s）'
                                   % (type(err).__name__, str(err)[:200]))
