# -*- coding: utf-8 -*-
"""流程清單與可選欄位清單。

欄位名稱的來源（實測結論，別再重掃一次）：

  單頭欄位  沿用 4_db_viewer 的做法，即 bpm_kb.extract.parse_form
            → core.form_handler 的 lbl_<id> / pairId 配對。
            新表單（設計時有填標籤 textValue）命中率高，舊表單很低：
            依單據數排前 25 張表單實測，整體只有 45%（414/923）。
            配不到就顯示欄位 id —— 不用座標鄰近去猜，實測會配錯
            （s_DeptID_txt 會被配成「部門名稱」，正確是「部門代號」）。

  明細欄位  ListElementDefinition/listItems/ListItem 的 <caption>，
            這是設計師實際填的欄位標題，可靠，實測 100% 有中文。
            form_handler 不解析這一層，故本模組自己取。

可選欄位清單「以定義為主、實際單據抽樣補充」：表單改版後舊單可能帶著
定義裡已經不存在的欄位，只看定義會讓那些欄位查不到也匯不出來。
"""

import re

from . import cache, db, form_xml, settings

settings.ensure_bpm_kb()

from bpm_kb import extract  # noqa: E402
from core import form_handler  # noqa: E402  （extract 已把 1_xml_tool 加進 sys.path）

# ListItem 的欄位定義；elementDefinition 內含大量樣式設定，先整段挖掉再取
_LIST_ITEM_RE = re.compile(
    r'<com\.dsc\.nana\.domain\.form\.ListItem>(.*?)'
    r'</com\.dsc\.nana\.domain\.form\.ListItem>', re.S)
_ELEMENT_DEF_RE = re.compile(r'<elementDefinition.*?</elementDefinition>', re.S)
_LIST_BLOCK_RE = re.compile(
    r'<com\.dsc\.nana\.domain\.form\.ListElementDefinition>(.*?)'
    r'</com\.dsc\.nana\.domain\.form\.ListElementDefinition>', re.S)

# 這些型別不是資料欄位，不該出現在「可查詢／可匯出」的清單裡
NON_DATA_TYPES = frozenset(('LABEL', 'BUTTON', 'HORIZONTAL_LINE', 'IMAGE', 'TITLE'))

PROCESS_LIST_SQL = """
SELECT processDefinitionId AS processId,
       MAX(processInstanceName) AS processName,
       COUNT(*) AS instanceCount,
       MIN(createdTime) AS firstCreated,
       MAX(createdTime) AS lastCreated
FROM ProcessInstance
GROUP BY processDefinitionId
"""

# 取這支流程最近的幾張單：既用來確認掛哪張表單，也用來補定義外的欄位
SAMPLE_SQL = """
SELECT TOP (?) l.id AS formId, CAST(f.fieldValues AS nvarchar(max)) AS fieldValues
FROM ProcessInstance p
JOIN LocalRelevantData l ON l.containerOID = p.contextOID
JOIN FormInstance f ON f.OID = l.valueOID
WHERE p.processDefinitionId = ?
ORDER BY p.createdTime DESC
"""


def _child(body, tag):
    match = re.search(r'<%s>(.*?)</%s>' % (tag, tag), body, re.S)
    return match.group(1).strip() if match else ''


def grid_columns(form_xml_text):
    """從表單定義取出表格控件的欄位標題。

    回傳 {明細欄位id: 標題}。表格控件本身的 id 不在 ListItem 裡，
    故這裡只建一份平面對照，夠匯出用。
    """
    columns = {}
    for block in _LIST_BLOCK_RE.finditer(form_xml_text):
        for item in _LIST_ITEM_RE.finditer(block.group(1)):
            body = _ELEMENT_DEF_RE.sub('', item.group(1))
            item_id = _child(body, 'id')
            if not item_id:
                continue
            columns[item_id] = _child(body, 'caption') or item_id
    return columns


# ---------------------------------------------------------------- 流程清單

def list_processes(host=None, keyword='', limit=500):
    """有單據的流程清單。以 ProcessInstance 為準 —— 沒開過單的流程匯不出東西。"""
    def produce():
        with db.connect(host) as database:
            rows = database.query(PROCESS_LIST_SQL)
        rows.sort(key=lambda r: -(r['instanceCount'] or 0))
        return rows

    rows = cache.get_or_set(db.cache_key(host, 'processes'), produce)

    keyword = (keyword or '').strip().lower()
    if keyword:
        rows = [r for r in rows
                if keyword in (r['processId'] or '').lower()
                or keyword in (r['processName'] or '').lower()]
    return rows[:limit], len(rows)


# ---------------------------------------------------------------- 表單定義

def _form_rows(host=None):
    """{表單id: 中繼資料}，已發佈的最新版優先。"""
    def produce():
        with db.connect(host) as database:
            released = extract.list_forms(database, latest_only=True, released_only=True)
            latest = extract.list_forms(database, latest_only=True)
        index = {}
        for row in latest:
            index[(row.get('id') or '').strip()] = row
        # 已發佈版覆蓋掉「最新但修訂中」的版本 —— 線上跑的是已發佈版
        for row in released:
            index[(row.get('id') or '').strip()] = row
        return index

    return cache.get_or_set(db.cache_key(host, 'form_rows'), produce)


def form_definition(host, form_id):
    """單一表單的欄位定義與表格欄位標題。查無定義時 missing 為 True，不假裝有。"""
    def produce():
        row = _form_rows(host).get(form_id)
        if row is None:
            return {'fields': [], 'gridColumns': {}, 'formName': '',
                    'version': None, 'missing': True}
        with db.connect(host) as database:
            parsed = extract.parse_form(database, row)
            xml_text = extract.fetch_form_xml(database, row['OID']) or ''
        return {
            'fields': parsed.get('fields', []),
            'gridColumns': grid_columns(xml_text),
            'formName': (row.get('formDefinitionName') or '').strip(),
            'version': row.get('version'),
            'missing': False,
        }

    return cache.get_or_set(db.cache_key(host, 'form_def:%s' % form_id), produce)


# ---------------------------------------------------------------- 欄位清單

def field_catalog(host, process_id):
    """這支流程可查詢／可匯出的欄位清單。

    每個欄位都標明名稱從哪來，讓使用者知道哪些是查得到的中文、
    哪些只有欄位 id —— 不把 id 混充成名稱。
    """
    def produce():
        with db.connect(host) as database:
            return database.query(SAMPLE_SQL,
                                  (settings.FIELD_SAMPLE_ROWS, process_id))

    samples = cache.get_or_set(db.cache_key(host, 'samples:%s' % process_id), produce)

    # 抽樣單據實際觀察到的欄位與表格
    seen_fields = []
    seen_grid_items = {}
    form_ids = []
    parse_failures = 0
    for row in samples:
        form_id = (row.get('formId') or '').strip()
        if form_id and form_id not in form_ids:
            form_ids.append(form_id)
        parsed = form_xml.safe_parse(row.get('fieldValues'))
        if parsed['error']:
            parse_failures += 1
            continue
        for field_id in parsed['order']:
            if field_id not in seen_fields:
                seen_fields.append(field_id)
        for grid_id, records in parsed['grids'].items():
            bucket = seen_grid_items.setdefault(grid_id, [])
            for record in records:
                for item_id in record:
                    if item_id not in bucket:
                        bucket.append(item_id)

    # 定義端
    definitions = {}
    grid_captions = {}
    forms_meta = []
    for form_id in form_ids:
        definition = form_definition(host, form_id)
        forms_meta.append({
            'formId': form_id,
            'formName': definition['formName'],
            'version': definition['version'],
            'missing': definition['missing'],
        })
        for field in definition['fields']:
            if field.get('id') and field['id'] not in definitions:
                definitions[field['id']] = field
        grid_captions.update(definition['gridColumns'])

    # 合併：定義順序在前（那是設計師排的版面順序），單據多出來的接在後面
    fields = []
    used = set()
    for form_id in form_ids:
        for field in form_definition(host, form_id)['fields']:
            field_id = field.get('id')
            if not field_id or field_id in used:
                continue
            if field.get('type') in NON_DATA_TYPES:
                continue
            used.add(field_id)
            name = field.get('name') or field_id
            fields.append({
                'id': field_id,
                'name': name,
                'type': field.get('type') or '',
                'named': name != field_id,
                'source': 'definition' if field_id in seen_fields else 'definition_only',
            })
    for field_id in seen_fields:
        if field_id in used or field_id in seen_grid_items:
            continue
        used.add(field_id)
        fields.append({'id': field_id, 'name': field_id, 'type': '',
                       'named': False, 'source': 'instance_only'})

    grids = []
    for grid_id, item_ids in seen_grid_items.items():
        grids.append({
            'id': grid_id,
            'name': (definitions.get(grid_id) or {}).get('name') or grid_id,
            'columns': [{'id': item_id,
                         'name': grid_captions.get(item_id, item_id),
                         'named': item_id in grid_captions}
                        for item_id in item_ids],
        })

    named = sum(1 for f in fields if f['named'])
    return {
        'processId': process_id,
        'forms': forms_meta,
        'fields': fields,
        'grids': grids,
        'sampled': len(samples),
        'parseFailures': parse_failures,
        'labelCoverage': {'named': named, 'total': len(fields)},
    }


def labels_for_definition(host, definition_oid):
    """用 FormInstance.definitionOID 取「這張單當時那一版」的欄位名稱。

    做法沿用 6_todo_viewer：版本落差會讓欄位名對不上，單張單既然知道自己用哪一版，
    就不該退而求其次去讀表單的最新版。

    匯出時做不到這件事 —— 一份 Excel 只有一列表頭，跨年份的單會用到不同版定義，
    故匯出的表頭固定取最新已發佈版；差異只影響改過名稱的欄位。
    """
    definition_oid = (definition_oid or '').strip()
    if not definition_oid:
        return {}, {}

    def produce():
        with db.connect(host) as database:
            xml_text = extract.fetch_form_xml(database, definition_oid) or ''
        if not xml_text:
            return {}, {}
        summary = form_handler.extract_text(xml_text, definition_oid)
        fields = {}
        for index, field in enumerate(summary.get('fields', [])):
            if field.get('id'):
                fields[field['id']] = {'name': field['name'], 'type': field['type'],
                                       'order': index}
        return fields, grid_columns(xml_text)

    return cache.get_or_set(db.cache_key(host, 'form_ver:%s' % definition_oid), produce)
