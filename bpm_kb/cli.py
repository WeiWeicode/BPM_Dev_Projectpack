# -*- coding: utf-8 -*-
"""bpm_kb 命令列介面。

    python bpm_kb_tool.py check              測試連線並顯示設定
    python bpm_kb_tool.py probe              探索資料表，寫出 schema 快照
    python bpm_kb_tool.py forms [關鍵字]      列出表單定義與版本
    python bpm_kb_tool.py processes [關鍵字]  列出流程定義與版本
    python bpm_kb_tool.py pull [關鍵字]       把表單與流程 XML 撈到 out/ 並解析
    python bpm_kb_tool.py digest             產生 docs/BPM_知識重點.md
    python bpm_kb_tool.py sql "SELECT ..."   臨時查詢（僅允許 SELECT）

共用選項（forms / processes / pull）：
    --days=N   只看 N 天內建立的版本（預設 7，鼎新改版後舊單結構未必相同）
    --all      不限日期
    --latest   每個 id 只留最新版本
"""

import io
import json
import os
import sys

from . import config, digest, extract, probe, process_graph
from .db import Database

OK = '✔'
NG = '✘'
LINE = '=' * 60
DEFAULT_DAYS = 7


def _setup_console():
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name)
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def _split_options(args):
    """把 --days=N / --all / --latest 從位置參數中拆出來。"""
    options = {'since_days': DEFAULT_DAYS, 'latest_only': False}
    rest = []
    for arg in args:
        if arg == '--all':
            options['since_days'] = None
        elif arg == '--latest':
            options['latest_only'] = True
        elif arg.startswith('--days='):
            options['since_days'] = int(arg.split('=', 1)[1])
        else:
            rest.append(arg)
    return rest, options


def _scope(options):
    parts = ['近 %d 天' % options['since_days'] if options['since_days'] else '全部日期']
    if options['latest_only']:
        parts.append('僅最新版')
    return '、'.join(parts)


def _print_rows(rows, limit=200):
    if not rows:
        print('（無資料）')
        return
    headers = list(rows[0].keys())
    widths = [len(h) for h in headers]
    body = []
    for row in rows[:limit]:
        cells = ['' if row[h] is None else str(row[h]) for h in headers]
        cells = [c if len(c) <= 40 else c[:37] + '...' for c in cells]
        body.append(cells)
        widths = [max(w, len(c)) for w, c in zip(widths, cells)]
    print('  '.join(h.ljust(w) for h, w in zip(headers, widths)))
    print('  '.join('-' * w for w in widths))
    for cells in body:
        print('  '.join(c.ljust(w) for c, w in zip(cells, widths)))
    if len(rows) > limit:
        print('... 共 %d 筆，僅顯示前 %d 筆' % (len(rows), limit))


def cmd_check(_args):
    print('連線設定：%s' % config.describe())
    with Database() as database:
        version = database.scalar('SELECT @@VERSION')
        name = database.scalar('SELECT DB_NAME()')
        tables = probe.list_tables(database)
    filled = [t for t in tables if (t['row_count'] or 0) > 0]
    print('%s 已連線 資料庫=%s' % (OK, name))
    print('   %s' % (version or '').splitlines()[0])
    print('   資料表 %d 張，其中 %d 張有資料' % (len(tables), len(filled)))
    return 0


def cmd_probe(_args):
    with Database() as database:
        path, data = probe.snapshot(database)
    hits = data['definition_columns']
    print('%s 快照已寫入 %s' % (OK, path))
    print('   資料表 %d 張、外鍵 %d 條' % (len(data['tables']), len(data['foreign_keys'])))
    print('%s 找到 %d 個序列化定義欄位：' % (OK, len(hits)))
    for hit in sorted(hits, key=lambda h: -h['row_count']):
        print('   %-32s %-16s %s (%s 筆)'
              % (hit['table_name'], hit['column_name'], hit['java_class'], hit['row_count']))
    return 0


def cmd_forms(args):
    args, options = _split_options(args)
    keyword = args[0] if args else ''
    print('來源：%s.%s（%s）' % (extract.FORM_TABLE, extract.FORM_XML_COLUMN, _scope(options)))
    with Database() as database:
        _print_rows(extract.list_forms(database, keyword, **options))
    return 0


def cmd_processes(args):
    args, options = _split_options(args)
    keyword = args[0] if args else ''
    print('來源：ProcessPackage + ProcessDefinition.%s（%s）'
          % (extract.PROCESS_XML_COLUMN, _scope(options)))
    with Database() as database:
        _print_rows(extract.list_processes(database, keyword, **options))
    return 0


def _write_json(path, payload):
    json_path = os.path.splitext(path)[0] + '.json'
    with io.open(json_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return json_path


def _pull_forms(database, rows):
    """表單：defSerialize 就是完整定義，落地後直接用 core.form_handler 解析。"""
    summaries = []
    for row in rows:
        path = extract.dump_form(database, row)
        if not path:
            print('   %s %s v%s 無 XML 內容，略過'
                  % (NG, row.get('id'), row.get('version')))
            continue
        try:
            summary = extract.summarize_form(path)
        except Exception as exc:
            print('   %s %s 解析失敗：%s' % (NG, os.path.basename(path), exc))
            continue
        summary['_source'] = {'oid': str(row.get('OID', '')).strip(),
                              'version': row.get('version'),
                              'publicationStatus': row.get('publicationStatus'),
                              'createdTime': row.get('createdTime')}
        summaries.append(summary)
        _write_json(path, summary)
        print('   %s %s' % (OK, os.path.basename(path)))
    print('%s 表單 共 %d 份' % (OK, len(summaries)))
    return summaries


def _pull_processes(database, rows):
    """流程：bpmXML 只有版面，邏輯要從關聯表組回來。"""
    summaries = []
    for row in rows:
        path = extract.dump_process(database, row)  # 保留原始 bpmXML 供比對
        graph = process_graph.build(database, row)
        if not graph:
            print('   %s %s v%s 找不到主流程定義，略過'
                  % (NG, row.get('id'), row.get('version')))
            continue
        graph['_source'] = {'oid': str(row.get('OID', '')).strip(),
                            'processDefinitionOID':
                                str(row.get('processDefinitionOID', '')).strip(),
                            'bpmXMLFile': os.path.basename(path) if path else ''}
        summaries.append(graph)
        stem = os.path.join(config.PROCESS_DIR,
                            '%s_v%s' % (extract._safe(row.get('id')), row.get('version')))
        _write_json(stem + '.json', graph)
        print('   %s %s v%s（關卡 %d、連線 %d）'
              % (OK, graph['processId'], graph['version'],
                 len(graph['activities']), len(graph['transitions'])))
    print('%s 流程 共 %d 份' % (OK, len(summaries)))
    return summaries


def cmd_pull(args):
    args, options = _split_options(args)
    keyword = args[0] if args else ''
    print('範圍：%s' % _scope(options))
    with Database() as database:
        print('%s 匯出表單' % LINE)
        forms = _pull_forms(database, extract.list_forms(database, keyword, **options))
        print('%s 匯出流程' % LINE)
        processes = _pull_processes(database,
                                    extract.list_processes(database, keyword, **options))
        path = digest.build(database, forms, processes, options=options)
    print('%s 重點整理：%s' % (OK, path))
    return 0


def _load_cached_summaries():
    """讀 out/ 內既有的解析結果，避免每次都重新連線撈 XML。"""
    forms, processes = [], []
    for directory, bucket in ((config.FORM_DIR, forms), (config.PROCESS_DIR, processes)):
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith('.json'):
                continue
            with io.open(os.path.join(directory, name), encoding='utf-8') as fh:
                bucket.append(json.load(fh))
    return forms, processes


def cmd_digest(args):
    _args, options = _split_options(args)
    forms, processes = _load_cached_summaries()
    with Database() as database:
        path = digest.build(database, forms, processes, options=options)
    print('%s 已產生 %s' % (OK, path))
    return 0


def cmd_sql(args):
    if not args:
        print('%s 請提供 SQL，例如：python bpm_kb_tool.py sql "SELECT TOP 5 * FROM FormDefinition"'
              % NG)
        return 1
    sql = ' '.join(args).strip()
    if not sql.lstrip('(').lower().startswith(('select', 'with')):
        print('%s 只接受 SELECT / WITH 查詢' % NG)
        return 1
    with Database() as database:
        _print_rows(database.query(sql))
    return 0


COMMANDS = {
    'check': cmd_check,
    'probe': cmd_probe,
    'forms': cmd_forms,
    'processes': cmd_processes,
    'pull': cmd_pull,
    'digest': cmd_digest,
    'sql': cmd_sql,
}


def main(argv=None):
    _setup_console()
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(__doc__.strip())
        return 0
    command = argv.pop(0)
    handler = COMMANDS.get(command)
    if handler is None:
        print('%s 未知指令：%s' % (NG, command))
        print(__doc__.strip())
        return 1
    try:
        return handler(argv)
    except config.ConfigError as exc:
        print('%s %s' % (NG, exc))
        return 1
