# -*- coding: utf-8 -*-
"""從資料庫萃取表單與流程定義，落地成檔案並轉成結構化摘要。

資料模型（由 probe 實測得出，非猜測）：

  表單  FormDefinition
        defSerialize 存整份 .form XML；版本欄位就在同一張表
        containerOID = 表單的邏輯身分，同一張表單的各版本共用

  流程  ProcessPackage                流程套件主檔（一個版本一筆）
        ├ ProcessPackageHeader        createdTime / vendor / bpmnVersion
        ├ RedefinableHeader           version / publicationStatus / authorName
        └ ProcessPackage_ProcessDef   → ProcessDefinition
                                        bpmXML 存整份 .bpmn XML

  表單與流程的關聯不在資料表，而在 bpmXML 內：每個關卡帶 formId 與
  formFieldAccessControl，決定該關卡看到的表單欄位權限。

萃取出來的 XML 直接餵給既有的 core.form_handler / core.bpmn_handler，
共用同一套解析邏輯，避免兩份實作各自漂移。
"""

import io
import os
import re
import sys

from . import config, db  # noqa: E402

sys.path.insert(0, config.XML_TOOL_DIR)

from core import bpmn_handler, form_handler  # noqa: E402

FORM_TABLE = 'FormDefinition'
FORM_XML_COLUMN = 'defSerialize'
# 表單的附屬大欄位：與 defSerialize 分開存，改欄位 ID 時必須一起處理
FORM_EXTRA_COLUMNS = ('script', 'mobileScript', 'rwdLayout', 'multiZhMap',
                      'scriptInfo', 'mobileScriptInfo')

PROCESS_TABLE = 'ProcessPackage'
PROCESS_XML_COLUMN = 'bpmXML'

SAFE_NAME = re.compile(r'[^A-Za-z0-9_一-鿿\-]+')

FORM_LIST_SQL = """
SELECT f.OID, f.id, f.formDefinitionName, f.version, f.publicationStatus,
       f.createdTime, f.validFrom, f.validTo, f.containerOID, f.authorName,
       DATALENGTH(f.{xml}) / 2 AS xml_chars
FROM [{table}] f
"""

PROCESS_LIST_SQL = """
SELECT p.OID, p.id, p.processPackageName, r.version, r.publicationStatus,
       h.createdTime, r.authorName, p.mainProcessDefinitionId, p.flowType,
       d.OID AS processDefinitionOID,
       DATALENGTH(d.{xml}) / 2 AS xml_chars
FROM [{table}] p
LEFT JOIN ProcessPackageHeader h ON h.OID = p.headerOID
LEFT JOIN RedefinableHeader r ON r.OID = p.redefinableHeaderOID
LEFT JOIN ProcessPackage_ProcessDef link ON link.ProcessPackageOID = p.OID
LEFT JOIN ProcessDefinition d ON d.OID = link.ProcessDefinitionOID
                             AND d.id = p.mainProcessDefinitionId
"""

# 已發佈狀態；另一種是 UNDER_REVISION（修訂中）
RELEASED = 'RELEASED'

FORM_SEARCH_COLUMNS = ('f.id', 'f.formDefinitionName')
PROCESS_SEARCH_COLUMNS = ('p.id', 'p.processPackageName')


def _where(conditions):
    return ('\nWHERE ' + '\n  AND '.join(conditions)) if conditions else ''


def _filters(keyword, search_columns, date_column, since_days,
             status_column='', released_only=False):
    conditions, params = [], []
    if keyword:
        conditions.append('(' + ' OR '.join('%s LIKE ?' % c for c in search_columns) + ')')
        params.extend('%%%s%%' % keyword for _ in search_columns)
    if since_days:
        conditions.append('%s >= DATEADD(day, ?, GETDATE())' % date_column)
        params.append(-abs(int(since_days)))
    if released_only and status_column:
        conditions.append('%s = ?' % status_column)
        params.append(RELEASED)
    return conditions, params


def _latest_only(rows, key='id'):
    """每個 id 只留版本號最大的一筆。"""
    best = {}
    for row in rows:
        name = row.get(key)
        current = best.get(name)
        if current is None or (row.get('version') or 0) > (current.get('version') or 0):
            best[name] = row
    return sorted(best.values(), key=lambda r: (r.get('createdTime') is None,
                                                r.get('createdTime')), reverse=True)


def list_forms(database, keyword='', since_days=None, latest_only=False,
               released_only=False):
    """列出表單版本，預設由新到舊；released_only 只保留已發佈版本。"""
    conditions, params = _filters(keyword, FORM_SEARCH_COLUMNS, 'f.createdTime',
                                  since_days, 'f.publicationStatus', released_only)
    sql = (FORM_LIST_SQL.format(xml=FORM_XML_COLUMN, table=FORM_TABLE)
           + _where(conditions) + '\nORDER BY f.createdTime DESC, f.version DESC')
    rows = database.query(sql, tuple(params))
    return _latest_only(rows) if latest_only else rows


def list_processes(database, keyword='', since_days=None, latest_only=False,
                   released_only=False):
    """列出流程套件版本，預設由新到舊；released_only 只保留已發佈版本。

    流程的發佈狀態在 RedefinableHeader，不在 ProcessPackage 上。
    """
    conditions, params = _filters(keyword, PROCESS_SEARCH_COLUMNS, 'h.createdTime',
                                  since_days, 'r.publicationStatus', released_only)
    sql = (PROCESS_LIST_SQL.format(xml=PROCESS_XML_COLUMN, table=PROCESS_TABLE)
           + _where(conditions) + '\nORDER BY h.createdTime DESC, r.version DESC')
    rows = database.query(sql, tuple(params))
    return _latest_only(rows) if latest_only else rows


def fetch_form_xml(database, oid):
    sql = 'SELECT %s AS xml FROM [%s] WHERE OID = ?' % (
        db.big_text('[%s]' % FORM_XML_COLUMN), FORM_TABLE)
    rows = database.query(sql, (oid,))
    return rows[0]['xml'] if rows else ''


def fetch_process_xml(database, process_definition_oid):
    sql = 'SELECT %s AS xml FROM ProcessDefinition WHERE OID = ?' % (
        db.big_text('[%s]' % PROCESS_XML_COLUMN),)
    rows = database.query(sql, (process_definition_oid,))
    return rows[0]['xml'] if rows else ''


def fetch_form_extras(database, oid):
    """取 script / rwdLayout 等與 defSerialize 分開存的大欄位。"""
    selected = ', '.join('%s AS [%s]' % (db.big_text('[%s]' % c), c)
                         for c in FORM_EXTRA_COLUMNS)
    rows = database.query('SELECT %s FROM [%s] WHERE OID = ?' % (selected, FORM_TABLE),
                          (oid,))
    return rows[0] if rows else {}


def _safe(name):
    return SAFE_NAME.sub('_', (name or 'unnamed').strip())[:80]


def _write(out_dir, stem, extension, xml):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    path = os.path.join(out_dir, stem + extension)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(xml)
    return path


def dump_form(database, row):
    """把一個表單版本寫成 out/forms/<id>_v<n>.form。"""
    config.ensure_dirs()
    xml = fetch_form_xml(database, row['OID'])
    if not xml:
        return ''
    return _write(config.FORM_DIR, '%s_v%s' % (_safe(row.get('id')), row.get('version')),
                  '.form', xml)


def dump_process(database, row):
    """把一個流程版本寫成 out/processes/<id>_v<n>.bpmn。"""
    config.ensure_dirs()
    oid = row.get('processDefinitionOID')
    if not oid:
        return ''
    xml = fetch_process_xml(database, oid)
    if not xml:
        return ''
    return _write(config.PROCESS_DIR, '%s_v%s' % (_safe(row.get('id')), row.get('version')),
                  '.bpmn', xml)


def summarize_form(path):
    """用既有 core.form_handler 解析成欄位清單。"""
    return form_handler.extract(path)


def parse_form(database, row):
    """直接由資料庫取 XML 解析成欄位清單，不落地檔案。"""
    xml = fetch_form_xml(database, row['OID'])
    if not xml:
        return {}
    return form_handler.extract_text(xml, '%s v%s' % (row.get('id'), row.get('version')))


def form_index(database, form_ids, since_days=None):
    """建立 {表單ID: {元件ID: {'name': ..., 'type': ...}}}。

    供關卡權限做型別對照 —— 判斷某個元件是不是按鈕，靠表單定義的型別，
    不靠 ID 命名猜測。同一表單有多版時取已發佈的最新版（見 PLAN.md 3.4）。
    """
    wanted = {fid for fid in form_ids if fid}
    if not wanted:
        return {}
    rows = list_forms(database, since_days=since_days, latest_only=True,
                      released_only=True)
    index = {}
    for row in rows:
        form_id = (row.get('id') or '').strip()
        if form_id not in wanted or form_id in index:
            continue
        summary = parse_form(database, row)
        index[form_id] = {f['id']: {'name': f['name'], 'type': f['type']}
                          for f in summary.get('fields', []) if f.get('id')}
    return index


def summarize_process(path):
    """用既有 core.bpmn_handler 解析成關卡與欄位權限清單。"""
    return bpmn_handler.extract(path)
