# -*- coding: utf-8 -*-
"""把探索與萃取結果整理成一份 AI／人都讀得懂的重點文件。

產出 docs/BPM_知識重點.md，依序回答五個問題：
  1. 定義存在哪裡（資料表與欄位）
  2. 版本怎麼運作
  3. 目前有哪些表單與流程
  4. 表單與流程怎麼扣在一起（關卡 × 欄位權限）
  5. 這個庫的資料表全景
"""

import io
import os

from . import config, extract, probe, process_graph

DOC_PATH = os.path.join(config.DOC_DIR, 'BPM_知識重點.md')
TOP_TABLES = 40


def _fmt(value):
    if value is None:
        return ''
    return str(value).replace('|', r'\|').strip()


def _table(headers, rows):
    if not rows:
        return '（無資料）'
    lines = ['| ' + ' | '.join(headers) + ' |',
             '| ' + ' | '.join('---' for _ in headers) + ' |']
    for row in rows:
        lines.append('| ' + ' | '.join(_fmt(c) for c in row) + ' |')
    return '\n'.join(lines)


MAX_LIST_ROWS = 100


def _rows_table(rows, columns, limit=MAX_LIST_ROWS):
    header = [c for c in columns if rows and c in rows[0]]
    text = _table(header, [[row.get(c) for c in header] for row in rows[:limit]])
    if len(rows) > limit:
        text += '\n\n（共 %d 筆，僅列出最新的 %d 筆）' % (len(rows), limit)
    return text


def _section_storage(snapshot):
    known = [
        ('FormDefinition', 'defSerialize', '表單定義 XML —— 匯出的 `.form` 本體'),
        ('FormDefinition', 'script / mobileScript', '表單 JS，與 XML 分開存'),
        ('FormDefinition', 'rwdLayout', 'RWD 版面配置'),
        ('FormDefinition', 'multiZhMap', '多語系字串對照'),
        ('ProcessDefinition', 'bpmXML', '**只有畫布座標**（Diagram / Node / Bounds），不含邏輯'),
        ('ActivityDefinition', '（關聯欄位）', '關卡本體：名稱、執行方式、執行者'),
        ('TransitionDefinition', '（關聯欄位）', '關卡之間的連線與條件'),
        ('FormFieldAccessDefinition', 'formFieldAccessControl', '每個關卡的欄位／按鈕權限'),
        ('ParticipantDefinition', '（關聯欄位）', '執行者定義（簽核對象怎麼算）'),
        ('（多張表）', 'bundleContainer', '多語系資源包，不是定義本體'),
    ]
    text = _table(['資料表', '欄位', '內容'], known)
    text += ('\n\n> 關鍵差異：**表單是整份 XML 存一格，流程是拆進關聯表**。\n'
             '> 匯出的 `.bpmn` 檔是設計師把關聯表重新序列化出來的結果，\n'
             '> 資料庫裡並沒有一個欄位長得跟它一樣。')
    hits = snapshot.get('definition_columns') or []
    if hits:
        found = [(h['table_name'], h['column_name'], h['java_class'], h['row_count'])
                 for h in sorted(hits, key=lambda h: -h['row_count'])]
        text += ('\n\n探索器實際抽樣到的 `com.dsc.*` 序列化欄位：\n\n'
                 + _table(['資料表', '欄位', 'Java 類別', '筆數'], found))
    return text


def _section_tables(snapshot):
    tables = [t for t in snapshot.get('tables', []) if (t['row_count'] or 0) > 0]
    tables.sort(key=lambda t: -(t['row_count'] or 0))
    rows = [(t['table_name'], t['row_count']) for t in tables[:TOP_TABLES]]
    note = ''
    if len(tables) > TOP_TABLES:
        note = '\n\n（僅列出筆數前 %d 名，共 %d 張有資料的表）' % (TOP_TABLES, len(tables))
    return _table(['資料表', '筆數'], rows) + note


def _permission_summary(items):
    """把欄位權限壓成「權限：數量」的短描述。"""
    counts = {}
    for item in items:
        counts[item['permission']] = counts.get(item['permission'], 0) + 1
    return '、'.join('%s×%d' % (k, v) for k, v in sorted(counts.items())) or '-'


def _section_flow(graph):
    """單一流程：關卡順序、執行者、掛哪張表單。"""
    rows = []
    for activity in process_graph.order_activities(graph):
        performers = '、'.join(sorted({p.get('participantType', '')
                                      for p in activity['performers']})) or '-'
        rows.append((activity['id'], activity['name'], activity['bpmnType'],
                     activity['performType'], performers,
                     activity['formId'] or '-',
                     _permission_summary(activity['fieldPermissions']),
                     len(activity['buttons'])))
    flow = ' → '.join(a['id'] for a in process_graph.order_activities(graph))
    return ('#### %s v%s　%s（%s，%s）\n\n`%s`\n\n%s'
            % (graph['processId'], graph['version'], graph['processName'],
               graph['flowType'], graph['publicationStatus'], flow,
               _table(['關卡 ID', '名稱', 'BPMN 型別', '執行方式', '執行者',
                       '表單', '欄位權限', '按鈕數'], rows)))


def _section_links(process_summaries, form_summaries):
    if not process_summaries:
        return '（尚未萃取流程，請先執行 `python bpm_kb_tool.py pull`）'
    known_forms = {f.get('formId') for f in form_summaries or []}
    parts = []
    for graph in process_summaries:
        if not graph.get('activities'):
            continue
        parts.append(_section_flow(graph))
    missing = sorted({a.get('formId') for g in process_summaries
                      for a in g.get('activities', [])
                      if a.get('formId') and a['formId'] not in known_forms})
    if missing:
        parts.append('> 下列表單被流程參照，但不在本次萃取範圍內：%s'
                     % '、'.join('`%s`' % m for m in missing))
    return '\n\n'.join(parts) or '（流程無關卡資料）'


def _section_permissions(process_summaries, limit=1):
    """挑一個流程，把「關卡 × 欄位」權限矩陣攤開，作為權限機制的樣本。"""
    graphs = [g for g in process_summaries or [] if g.get('activities')]
    if not graphs:
        return '（尚未萃取流程）'
    graph = graphs[0]
    activities = [a for a in process_graph.order_activities(graph)
                  if a.get('fieldPermissions') or a.get('buttons')]
    if not activities:
        return '（此流程未設定欄位權限）'
    field_ids = []
    for activity in activities:
        for item in activity['fieldPermissions'] + activity['buttons']:
            if item['id'] not in field_ids:
                field_ids.append(item['id'])
    headers = ['欄位 ID'] + [a['name'] or a['id'] for a in activities]
    rows = []
    for field_id in field_ids:
        cells = [field_id]
        for activity in activities:
            lookup = {i['id']: i['permission']
                      for i in activity['fieldPermissions'] + activity['buttons']}
            cells.append(lookup.get(field_id, '—'))
        rows.append(cells)
    return ('以 `%s` v%s 為例：\n\n%s\n\n'
            '權限值取自資料庫實測（取樣 20000 筆 FormFieldAccessDefinition）：\n'
            '`ENABLED`（可編輯，~98%%）、`INVISIBLE`（隱藏）、`FULL_CONTROL`（完全控制）。\n'
            '未列出者以 `—` 表示 —— 對照 BPM 設計師 UI 確認，這代表**唯讀(Disable)**，\n'
            '不是「沿用表單預設」。要把元件設成唯讀，作法是把它從權限字串中移除。'
            % (graph['processId'], graph['version'], _table(headers, rows)))


def _section_form_fields(form_summaries, limit=2):
    if not form_summaries:
        return '（尚未萃取表單）'
    parts = []
    for summary in form_summaries[:limit]:
        rows = [(f.get('id'), f.get('name'), f.get('type'))
                for f in summary.get('fields', [])]
        parts.append('#### %s（%s，共 %d 個元件）\n\n%s'
                     % (summary.get('formId'), summary.get('formName'), len(rows),
                        _table(['元件 ID', '顯示名稱', '型別'], rows)))
    if len(form_summaries) > limit:
        parts.append('（另有 %d 張表單，明細見 `out/forms/*.json`）'
                     % (len(form_summaries) - limit))
    return '\n\n'.join(parts)


def build(database, form_summaries=None, process_summaries=None, snapshot=None,
          options=None):
    """組出整份文件並寫檔，回傳路徑。"""
    config.ensure_dirs()
    snapshot = snapshot or probe.load_snapshot() or {}
    options = options or {}
    since_days = options.get('since_days')
    scope = ('近 %d 天建立的版本' % since_days) if since_days else '全部版本'

    forms = extract.list_forms(database, since_days=since_days)
    processes = extract.list_processes(database, since_days=since_days)

    parts = [
        '# 鼎新 BPM 資料模型重點整理',
        '',
        '> 由 `bpm_kb` 自動產生。資料來源：`%s`，範圍：%s。'
        % (config.describe(database.settings), scope),
        '',
        '## 1. 定義存在哪裡',
        '',
        _section_storage(snapshot),
        '',
        '## 2. 版本怎麼運作',
        '',
        '### 表單：版本欄位就在 FormDefinition 自己身上',
        '',
        '同一個 `id` 有多筆記錄，`version` 遞增；`containerOID` 是表單的邏輯身分，',
        '同一張表單的各版本共用同一個 `containerOID`。`publicationStatus` 為',
        '`RELEASED`（已發佈）或 `UNDER_REVISION`（修訂中），`validFrom` / `validTo`',
        '決定生效區間。`objectVersion` 是 O/R mapping 的樂觀鎖，與表單版本無關。',
        '',
        '### 流程：版本資訊拆在 header 表',
        '',
        '```',
        'ProcessPackage                     流程套件，一個版本一筆',
        ' ├─ headerOID            → ProcessPackageHeader   createdTime / bpmnVersion',
        ' ├─ redefinableHeaderOID → RedefinableHeader      version / publicationStatus',
        ' └─ OID → ProcessPackage_ProcessDef → ProcessDefinition',
        '                                       OID 即各關聯表的 containerOID',
        '                                       bpmXML = 畫布座標',
        '',
        'ProcessDefinition.OID = containerOID 之下掛：',
        '   ActivityDefinition        關卡',
        '   TransitionDefinition      連線（from / to）',
        '   ParticipantDefinition     執行者',
        '```',
        '',
        '要重建一份流程，必須用 `containerOID` 把這幾張表撈齊 —— 這正是',
        '`bpm_kb/process_graph.py` 在做的事。',
        '',
        '## 3. 目前有哪些表單與流程',
        '',
        '### 表單（%s）' % scope,
        '',
        _rows_table(forms, ['id', 'formDefinitionName', 'version', 'publicationStatus',
                            'createdTime', 'xml_chars']),
        '',
        '### 流程（%s）' % scope,
        '',
        _rows_table(processes, ['id', 'processPackageName', 'version', 'publicationStatus',
                                'createdTime', 'flowType']),
        '',
        '## 4. 表單與流程如何扣在一起',
        '',
        '兩者之間沒有外鍵。關聯落在 `ActivityDefinition.formFieldAccessDefinitionOID`',
        '→ `FormFieldAccessDefinition.formFieldAccessControl`，內容是一段',
        '`<FormFieldAccessControl><表單ID><欄位ID>權限</欄位ID>…</表單ID></FormFieldAccessControl>`。',
        '所以「表單掛在哪個關卡」與「該關卡看得到什麼」是同一筆資料決定的。',
        '',
        _section_links(process_summaries, form_summaries),
        '',
        '### 關卡 × 欄位權限矩陣',
        '',
        _section_permissions(process_summaries),
        '',
        '### 表單欄位樣本',
        '',
        _section_form_fields(form_summaries),
        '',
        '## 5. 資料表全景',
        '',
        _section_tables(snapshot),
        '',
    ]
    text = '\n'.join(parts)
    with io.open(DOC_PATH, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return DOC_PATH
