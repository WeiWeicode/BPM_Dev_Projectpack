# -*- coding: utf-8 -*-
"""匯出：把查詢條件組成 Excel 位元組流。

三個項目（清單／內容／簽核名單）可任選，全部寫進同一個 Excel 的不同 tab。
表格控件的明細跟著「內容」一起出，每個表格自成一個 tab。

上限的意義：查詢本身很快（實測單一流程加日期區間 0.05 秒），
真正撐不住的是產出——逐欄展開後一列可能上百欄。超過上限就明確擋下來，
不會偷偷只匯前面幾筆讓人以為匯完了。
"""

import datetime

from . import catalog, db, excel, form_xml, query, settings


class ExportError(Exception):
    """使用者輸入或範圍造成的錯誤，由路由層轉成 400。"""


def _requested_fields(catalog_data, field_ids):
    """把選取的欄位 id 轉成 (id, 名稱)；沒指定就用全部可匯出欄位。"""
    index = {f['id']: f for f in catalog_data['fields']}
    if not field_ids:
        return [(f['id'], f['name']) for f in catalog_data['fields']]
    pairs = []
    missing = []
    for field_id in field_ids:
        field = index.get(field_id)
        if field is None:
            missing.append(field_id)
            continue
        pairs.append((field_id, field['name']))
    if missing:
        raise ExportError('這支流程的欄位清單裡沒有：%s' % '、'.join(missing))
    return pairs


def preview(host, params):
    """先算筆數再匯出 —— 讓人知道會拿到多大一份，超過上限就明說。"""
    start, end = query.date_range(params.get('startDate'), params.get('endDate'))
    total = query.count_candidates(host, params['processId'], start, end,
                                   params.get('filters'))
    custom = [c for c in (params.get('customFilters') or [])
              if c.get('fieldId') and (c.get('value') or '').strip()]
    return {
        'matched': total,
        'limit': settings.MAX_EXPORT_ROWS,
        'exceeded': total > settings.MAX_EXPORT_ROWS,
        'exact': not custom,
        'note': ('筆數為固定條件的結果；自訂欄位條件要逐張解析表單才算得出來，'
                 '實際匯出筆數會少於或等於這個數字。' if custom else ''),
    }


def collect(host, params, need_form, need_items):
    """撈出要匯出的單，並依需要補上表單內容與簽核歷程。"""
    start, end = query.date_range(params.get('startDate'), params.get('endDate'))
    custom = [c for c in (params.get('customFilters') or [])
              if c.get('fieldId') and (c.get('value') or '').strip()]

    limit = settings.MAX_EXPORT_ROWS
    scan_limit = settings.MAX_SCAN_ROWS if custom else limit
    rows, truncated = query.fetch_candidates(host, params['processId'], start, end,
                                             params.get('filters'),
                                             need_form or bool(custom), scan_limit)

    records = []
    for row in rows:
        parsed = (form_xml.safe_parse(row.get('fieldValues'))
                  if (need_form or custom) else
                  {'fields': {}, 'grids': {}, 'order': [], 'formId': '',
                   'wrapped': 0, 'error': ''})
        if custom and not parsed['error'] and not query.match_custom(parsed, custom):
            continue
        records.append({'summary': query.summarize(row, parsed if (need_form or custom) else None),
                        'parsed': parsed,
                        'items': [],
                        'progress': {}})
        if len(records) > limit:
            raise ExportError(
                '符合條件的單超過上限 %d 筆，請縮小日期區間或加上篩選條件後再匯出。'
                % limit)

    if truncated and not custom:
        raise ExportError('符合條件的單超過上限 %d 筆，請縮小日期區間或加上篩選條件後再匯出。'
                          % limit)

    # 簽核歷程與時程摘要都來自 WorkItem；清單 tab 的結案時間也靠它算，故一律取。
    context_oids = [r['summary']['contextOID'] for r in records]
    items_map = query.work_items(host, context_oids)
    for record in records:
        items = items_map.get(record['summary']['contextOID'], [])
        record['progress'] = query.progress(items)
        record['items'] = items if need_items else []

    return records, truncated


def run(host, params):
    """產生 Excel，回傳 (檔名, bytes, 統計)。"""
    want_list = bool(params.get('exportList'))
    want_content = bool(params.get('exportContent'))
    want_signatures = bool(params.get('exportSignatures'))
    if not (want_list or want_content or want_signatures):
        raise ExportError('至少要選一項匯出內容（清單／內容／簽核名單）。')

    process_id = (params.get('processId') or '').strip()
    if not process_id:
        raise ExportError('沒有指定流程。')

    catalog_data = catalog.field_catalog(host, process_id)
    selected_fields = []
    grids = []
    if want_content:
        selected_fields = _requested_fields(catalog_data, params.get('fieldIds'))
        wanted_grids = params.get('gridIds')
        grids = [g for g in catalog_data['grids']
                 if not wanted_grids or g['id'] in wanted_grids]

    records, truncated = collect(host, params, want_content, want_signatures)
    if not records:
        raise ExportError('這個條件查不到任何單，沒有東西可以匯出。')

    coverage = catalog_data['labelCoverage']
    meta = [
        ('資料來源', db_label(host)),
        ('流程', '%s（%s）' % (process_id, _process_name(records))),
        ('申請日期區間', '%s ~ %s' % (params.get('startDate'), params.get('endDate'))),
        ('固定條件', _describe_filters(params.get('filters'))),
        ('自訂欄位條件', _describe_custom(params.get('customFilters'), catalog_data)),
        ('匯出項目', '、'.join(filter(None, [
            '清單' if want_list else '',
            '內容（含表格明細）' if want_content else '',
            '簽核名單' if want_signatures else '']))),
        ('匯出筆數', len(records)),
        ('匯出時間', datetime.datetime.now()),
        ('欄位名稱覆蓋率',
         '%d / %d 個單頭欄位查得到中文名稱，其餘顯示欄位 ID（表單定義未填標籤）'
         % (coverage['named'], coverage['total'])),
        ('抽樣說明',
         '可選欄位清單取自表單定義，並以最近 %d 張單補上定義外的欄位' %
         catalog_data['sampled']),
    ]

    options = {
        'list': want_list,
        'content': want_content,
        'signatures': want_signatures,
        'selected_fields': selected_fields,
        'grids': grids,
        'catalog_fields': catalog_data['fields'],
        'meta': meta,
    }
    content = excel.build(records, options)
    filename = '%s_%s_%s.xlsx' % (
        process_id,
        (params.get('startDate') or '').replace('-', ''),
        (params.get('endDate') or '').replace('-', ''))
    stats = {'rows': len(records), 'truncated': truncated,
             'signatureRows': sum(len(r['items']) for r in records)}
    return filename, content, stats


def db_label(host):
    entry = settings.host_entry(host or settings.DEFAULT_HOST)
    return '%s（%s）' % (entry[1], db.describe(host))


def _process_name(records):
    for record in records:
        if record['summary'].get('processName'):
            return record['summary']['processName']
    return ''


def _describe_filters(filters):
    filters = filters or {}
    labels = [('processSerialNumber', '流程單號'), ('formSerialNumber', '表單單號'),
              ('requester', '申請人'), ('subject', '標題')]
    parts = ['%s 含「%s」' % (label, filters[key].strip())
             for key, label in labels if (filters.get(key) or '').strip()]
    states = filters.get('states') or []
    if states:
        parts.append('狀態為 %s' % '、'.join(
            query.state_name(query.PROCESS_STATE, s) for s in states))
    return '、'.join(parts) or '（無）'


def _describe_custom(custom_filters, catalog_data):
    index = {f['id']: f['name'] for f in catalog_data['fields']}
    parts = []
    for condition in custom_filters or []:
        field_id = condition.get('fieldId')
        value = (condition.get('value') or '').strip()
        if not field_id or not value:
            continue
        parts.append('%s（%s）含「%s」' % (index.get(field_id, field_id), field_id, value))
    return '、'.join(parts) or '（無）'
