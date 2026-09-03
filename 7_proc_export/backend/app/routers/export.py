# -*- coding: utf-8 -*-
"""匯出端點。

/preview 先給筆數，讓人在按下匯出前知道會拿到多大一份；
/download 產出 Excel。兩支都唯讀，POST 只是為了傳結構化的查詢條件。
"""

from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from .. import export, query
from ..schemas import ExportPreview, ExportRequest

router = APIRouter(prefix='/api/export', tags=['export'])

XLSX_MIME = ('application/vnd.openxmlformats-officedocument'
             '.spreadsheetml.sheet')


def _guard(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except (export.ExportError, query.QueryError) as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post('/preview', response_model=ExportPreview)
def preview(req: ExportRequest, host: Optional[str] = Query(None)):
    """先算筆數。超過上限時 exceeded 為 true，前端要擋住匯出鈕。"""
    return _guard(export.preview, host, req.model_dump())


@router.post('/download')
def download(req: ExportRequest, host: Optional[str] = Query(None)):
    """產生 Excel。清單／內容／簽核名單寫進同一個檔案的不同 tab。"""
    filename, content, stats = _guard(export.run, host, req.model_dump())
    # 檔名有中文，用 RFC 5987 的 filename* 才不會在下載時變成亂碼
    disposition = "attachment; filename=export.xlsx; filename*=UTF-8''%s" % quote(filename)
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={
            'Content-Disposition': disposition,
            'X-Export-Rows': str(stats['rows']),
            'X-Export-Signature-Rows': str(stats['signatureRows']),
        },
    )
