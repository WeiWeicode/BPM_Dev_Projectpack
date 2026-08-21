# -*- coding: utf-8 -*-
"""資料存取服務：呼叫 bpm_kb，組成 API 要回的結構。

一律唯讀，且只取已發佈（RELEASED）的最新版 —— 檢視器要呈現的是線上現況，
修訂中的版本會造成誤導。

效能上最需要注意的是 formFieldAccessControl 這個 ntext 欄位：
全部撈出來是 860 MB / 55 秒，但表單 ID 就寫在字串開頭，
只取前 200 字元建索引是 0.44 MB / 0.4 秒（見 _usage_index）。
"""

import re

from . import cache, settings

settings.ensure_bpm_kb()

from bpm_kb import extract, process_graph  # noqa: E402
from bpm_kb.db import Database, big_text  # noqa: E402

# formFieldAccessControl 開頭：<FormFieldAccessControl><表單ID>
FORM_ID_RE = re.compile(r'<FormFieldAccessControl>\s*<([\w.\-]+)>')

HEAD_LEN = 200

USAGE_SQL = """
SELECT a.containerOID AS container_oid, a.id AS activity_id,
       a.activityDefinitionName AS activity_name,
       LEFT(%s, %d) AS head
FROM ActivityDefinition a
JOIN FormFieldAccessDefinition fa ON fa.OID = a.formFieldAccessDefinitionOID
WHERE a.containerOID IN (%s)
"""


def _clean(value):
    return (value or '').strip() if isinstance(value, str) else value


# ---------------------------------------------------------------- 基礎清單

def _form_rows():
    """已發佈表單的最新版（中繼資料，不含 XML）。"""
    def produce():
        with Database() as database:
            return extract.list_forms(database, latest_only=True, released_only=True)
    return cache.get_or_set('form_rows', produce)


def _process_rows():
    """已發佈流程的最新版（中繼資料，不含 XML）。"""
    def produce():
        with Database() as database:
            return extract.list_processes(database, latest_only=True, released_only=True)
    return cache.get_or_set('process_rows', produce)


def _find(rows, key, value):
    for row in rows:
        if _clean(row.get(key)) == value:
            return row
    return None


def _form_summary(row):
    return {
        'form_id': _clean(row.get('id')),
        'form_name': _clean(row.get('formDefinitionName')),
        'version': row.get('version') or 0,
        'created_time': row.get('createdTime'),
    }


def _process_summary(row):
    return {
        'process_id': _clean(row.get('id')),
        'process_name': _clean(row.get('processPackageName')),
        'version': row.get('version') or 0,
        'flow_type': _clean(row.get('flowType')),
        'created_time': row.get('createdTime'),
    }


def _match(row, keyword, keys):
    if not keyword:
        return True
    low = keyword.lower()
    return any(low in (_clean(row.get(k)) or '').lower() for k in keys)


def _page(items, limit, offset):
    limit = min(max(int(limit or settings.DEFAULT_LIMIT), 1), settings.MAX_LIMIT)
    offset = max(int(offset or 0), 0)
    return items[offset:offset + limit], len(items)


# ---------------------------------------------------------------- 對外查詢

def health():
    try:
        with Database() as database:
            version = database.scalar('SELECT @@VERSION') or ''
            name = database.scalar('SELECT DB_NAME()') or ''
        from bpm_kb import config
        return {'ok': True, 'database': name, 'connection': config.describe(),
                'server_version': version.splitlines()[0].strip(),
                'cache': cache.stats(),
                'write_enabled': settings.ENABLE_WRITE,
                'writable_processes': list(settings.WRITABLE_PROCESSES)}
    except Exception as exc:                     # 連線失敗要如實回報，不假裝成功
        return {'ok': False, 'error': str(exc), 'cache': cache.stats(),
                'write_enabled': settings.ENABLE_WRITE,
                'writable_processes': list(settings.WRITABLE_PROCESSES)}


def list_forms(keyword='', limit=None, offset=0):
    rows = [r for r in _form_rows() if _match(r, keyword, ('id', 'formDefinitionName'))]
    page, total = _page(rows, limit, offset)
    return [_form_summary(r) for r in page], total


def list_processes(keyword='', limit=None, offset=0):
    rows = [r for r in _process_rows()
            if _match(r, keyword, ('id', 'processPackageName'))]
    page, total = _page(rows, limit, offset)
    return [_process_summary(r) for r in page], total


def get_form(form_id):
    """單一表單的元件明細：id / name / type。解析 XML，故有快取。"""
    row = _find(_form_rows(), 'id', form_id)
    if row is None:
        return None

    def produce():
        with Database() as database:
            return extract.parse_form(database, row)

    parsed = cache.get_or_set('form:%s' % form_id, produce)
    summary = _form_summary(row)
    fields = [{'id': f['id'], 'name': f['name'], 'type': f['type']}
              for f in parsed.get('fields', [])]
    summary['fields'] = fields
    summary['field_count'] = len(fields)
    return summary


def _usage_index():
    """{表單ID: [{container_oid, activity_id, activity_name}, ...]}。

    只取控制字串前 200 字元 —— 表單 ID 就在開頭，不需要整份 ntext。
    """
    def produce():
        rows = _process_rows()
        oids = [r['processDefinitionOID'] for r in rows if r.get('processDefinitionOID')]
        if not oids:
            return {}
        placeholders = ','.join('?' for _ in oids)
        sql = USAGE_SQL % (big_text('fa.formFieldAccessControl'), HEAD_LEN, placeholders)
        with Database() as database:
            hits = database.query(sql, tuple(oids))
        index = {}
        for hit in hits:
            match = FORM_ID_RE.search(hit.get('head') or '')
            if not match:
                continue
            index.setdefault(match.group(1), []).append({
                'container_oid': _clean(hit.get('container_oid')),
                'activity_id': _clean(hit.get('activity_id')),
                'activity_name': _clean(hit.get('activity_name')),
            })
        return index
    return cache.get_or_set('usage_index', produce)


def get_form_usage(form_id):
    """這張表單被哪些流程的哪些關卡使用。"""
    if _find(_form_rows(), 'id', form_id) is None:
        return None
    by_oid = {_clean(r.get('processDefinitionOID')): r for r in _process_rows()}
    usages = []
    for entry in _usage_index().get(form_id, []):
        row = by_oid.get(entry['container_oid'])
        if row is None:
            continue
        usages.append({
            'process_id': _clean(row.get('id')),
            'process_name': _clean(row.get('processPackageName')),
            'version': row.get('version') or 0,
            'activity_id': entry['activity_id'],
            'activity_name': entry['activity_name'],
        })
    usages.sort(key=lambda u: (u['process_id'], u['activity_id']))
    return usages


def _graph(process_id):
    """流程的完整結構，含表單型別 join。"""
    row = _find(_process_rows(), 'id', process_id)
    if row is None:
        return None

    def produce():
        with Database() as database:
            plain = process_graph.build(database, row)
            form_ids = {a['formId'] for a in plain.get('activities', []) if a['formId']}
            index = extract.form_index(database, form_ids) if form_ids else {}
            return process_graph.build(database, row, index)

    return cache.get_or_set('process:%s' % process_id, produce)


def get_process(process_id):
    graph = _graph(process_id)
    if graph is None:
        return None
    row = _find(_process_rows(), 'id', process_id)
    detail = _process_summary(row)
    detail['activities'] = [{
        'id': a['id'],
        'name': a['name'],
        'bpmn_type': a['bpmnType'],
        'perform_type': a['performType'],
        'performers': sorted({p.get('participantType', '') for p in a['performers']
                              if p.get('participantType')}),
        'form_id': a['formId'],
        'buttons': a['buttons'],
        'fields': a['fieldPermissions'],
    } for a in process_graph.order_activities(graph)]
    detail['transitions'] = [{'from': t['from'], 'to': t['to'],
                              'has_condition': t['hasCondition']}
                             for t in graph.get('transitions', [])]
    return detail


def _form_indexes(form_ids):
    """取多張表單的 {元件ID: {name, type}}，有快取。"""
    if not form_ids:
        return {}

    def produce():
        with Database() as database:
            return extract.form_index(database, form_ids)

    return cache.get_or_set('form_index:%s' % ','.join(sorted(form_ids)), produce)


def get_matrix(process_id, only='all'):
    """關卡 × 元件的權限矩陣。

    columns 收錄**所有掛了表單的關卡**，即使它一項權限都沒設 ——
    「全部唯讀」是合法狀態，濾掉的話使用者就再也改不回來。
    只有完全沒掛表單的關卡（權限字串為空）才排除。

    rows 以**表單定義**為準，不是以既有權限為準，這樣未設定的元件也看得到、改得動。
    """
    detail = get_process(process_id)
    if detail is None:
        return None
    columns = [a for a in detail['activities'] if a['form_id']]
    indexes = _form_indexes({a['form_id'] for a in columns})

    # 依表單定義順序建立列；同一流程可能有多張表單，依 columns 出現順序串接
    order, meta = [], {}
    for activity in columns:
        for field_id, info in (indexes.get(activity['form_id']) or {}).items():
            if field_id not in meta:
                order.append(field_id)
                meta[field_id] = {'name': info['name'], 'type': info['type'],
                                  'is_button': info['type'] == 'BUTTON'}

    # 權限清單裡有、但表單定義沒有的（orphaned）也要列出來，不能藏起來
    for activity in columns:
        for item in activity['buttons'] + activity['fields']:
            if item['id'] not in meta:
                order.append(item['id'])
                meta[item['id']] = {'name': item['name'], 'type': item['type'],
                                    'is_button': item['id'] in
                                    {b['id'] for b in activity['buttons']}}

    lookups = [{i['id']: i for i in a['buttons'] + a['fields']} for a in columns]

    rows = []
    for item_id in order:
        info = meta[item_id]
        if only == 'button' and not info['is_button']:
            continue
        if only == 'field' and info['is_button']:
            continue
        cells = []
        for activity, lookup in zip(columns, lookups):
            found = lookup.get(item_id)
            # 這個元件不屬於該關卡所掛的表單 -> 不適用，不能編輯
            applicable = item_id in (indexes.get(activity['form_id']) or {}) \
                or found is not None
            cells.append({'permission': found['permission'] if found else None,
                          'orphaned': bool(found and found['orphaned']),
                          'applicable': applicable})
        rows.append({'id': item_id, 'name': info['name'], 'type': info['type'],
                     'is_button': info['is_button'], 'cells': cells})

    return {'process_id': detail['process_id'], 'process_name': detail['process_name'],
            'version': detail['version'], 'columns': columns, 'rows': rows}


def search(query, limit=50, include_fields=False):
    """全域搜尋：表單、流程、關卡；include_fields 才會掃元件（需解析所有表單 XML）。"""
    low = (query or '').strip().lower()
    if len(low) < 2:
        return {'query': query, 'hits': [], 'truncated': False}

    hits = []
    for row in _form_rows():
        if _match(row, low, ('id', 'formDefinitionName')):
            hits.append({'kind': 'form', 'id': _clean(row.get('id')),
                         'name': _clean(row.get('formDefinitionName'))})
    for row in _process_rows():
        if _match(row, low, ('id', 'processPackageName')):
            hits.append({'kind': 'process', 'id': _clean(row.get('id')),
                         'name': _clean(row.get('processPackageName'))})

    by_oid = {_clean(r.get('processDefinitionOID')): r for r in _process_rows()}
    for form_id, entries in _usage_index().items():
        for entry in entries:
            if low not in entry['activity_id'].lower() \
                    and low not in entry['activity_name'].lower():
                continue
            row = by_oid.get(entry['container_oid'])
            if row is None:
                continue
            hits.append({'kind': 'activity', 'id': entry['activity_id'],
                         'name': entry['activity_name'],
                         'parent_id': _clean(row.get('id')),
                         'parent_name': _clean(row.get('processPackageName'))})

    if include_fields:
        hits.extend(_search_fields(low))

    truncated = len(hits) > limit
    return {'query': query, 'hits': hits[:limit], 'truncated': truncated}


def _search_fields(low):
    """掃所有已發佈表單的元件。第一次要解析全部 XML，很慢，故預設不啟用。"""
    def produce():
        rows = _form_rows()
        table = []
        with Database() as database:
            for row in rows:
                parsed = extract.parse_form(database, row)
                form_id = _clean(row.get('id'))
                for field in parsed.get('fields', []):
                    table.append((form_id, _clean(row.get('formDefinitionName')),
                                  field['id'], field['name']))
        return table

    table = cache.get_or_set('field_table', produce)
    return [{'kind': 'form_field', 'id': fid, 'name': fname,
             'parent_id': form_id, 'parent_name': form_name}
            for form_id, form_name, fid, fname in table
            if low in fid.lower() or low in (fname or '').lower()]
