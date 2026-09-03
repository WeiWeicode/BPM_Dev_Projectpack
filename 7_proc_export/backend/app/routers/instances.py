# -*- coding: utf-8 -*-
"""單據查詢端點。

search 用 POST 只是因為條件是結構化的（自訂欄位條件是一個陣列），
塞不進 query string —— 它一樣唯讀，不會改到任何資料。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import catalog, query
from ..schemas import InstanceDetail, SearchRequest, SearchResult

router = APIRouter(prefix='/api/instances', tags=['instances'])


def _guard(func, *args, **kwargs):
    """預期內的輸入錯誤轉成 400；其餘照常往上拋，不吞例外。"""
    try:
        return func(*args, **kwargs)
    except query.QueryError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post('/search', response_model=SearchResult)
def search(req: SearchRequest, host: Optional[str] = Query(None)):
    """查單。日期區間必填 —— 不限範圍的查詢在 55 萬列上沒有意義。

    有選 fieldIds 時，每一列會附上那些欄位的值，讓表格直接顯示自訂欄位。
    """
    result = _guard(query.search, host, req.processId, req.startDate, req.endDate,
                    req.filters.model_dump(), [c.model_dump() for c in req.customFilters],
                    req.page, req.pageSize)

    if req.fieldIds:
        # 表格要顯示自訂欄位時得帶值回去；只補這一頁的單，不重撈全部。
        serials = [r['processSerialNumber'] for r in result['rows']]
        values = query.values_for_serials(host, serials, req.fieldIds)
        for row in result['rows']:
            row['values'] = values.get(row['processSerialNumber'], {})

    result.setdefault('note', '')
    if result.get('truncated'):
        result['note'] = ('候選單數超過掃描上限，自訂欄位條件只比對了最近的部分單據，'
                          '請縮小日期區間取得完整結果。')
    return result


@router.get('/{process_serial_number}', response_model=InstanceDetail)
def load(process_serial_number: str, host: Optional[str] = Query(None)):
    """單張單的表單內容與簽核歷程。以流程單號查。"""
    record = query.load_instance(host, process_serial_number)
    if record is None:
        raise HTTPException(status_code=404,
                            detail='查無流程單號 %s' % process_serial_number)

    parsed = record['parsed']
    summary = record['summary']

    # 欄位名稱取自這張單當時那一版定義（FormInstance.definitionOID），
    # 不是表單的最新版 —— 改過版的表單，名稱會對不上。
    index, _grid_captions = catalog.labels_for_definition(
        host, record.get('formDefinitionOID'))
    if not index and parsed['formId']:
        # 那一版讀不到時退回最新已發佈版，並在 source 標明是退回來的
        definition = catalog.form_definition(host, parsed['formId'])
        index = {f['id']: f for f in definition['fields']}

    fields = []
    for field_id in parsed['order']:
        meta = index.get(field_id) or {}
        name = meta.get('name') or field_id
        fields.append({'id': field_id, 'name': name,
                       'type': meta.get('type') or '',
                       'named': name != field_id,
                       'source': 'definition' if meta else 'instance_only'})

    return {
        'summary': summary,
        'formId': parsed['formId'],
        'fields': fields,
        'values': parsed['fields'],
        'grids': parsed['grids'],
        'workItems': record['items'],
        'parseError': parsed['error'],
    }
