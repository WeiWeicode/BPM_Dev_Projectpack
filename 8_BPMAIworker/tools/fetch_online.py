# -*- coding: utf-8 -*-
"""從線上 BPM 資料庫抓一支流程與它用到的表單，落地成可參考的原檔與結構摘要。

為什麼要有這支：①～⑦ 都能查線上資料，但沒有一支把「流程 + 表單 + JavaScript」
一次抓齊放進同一個資料夾。⑧ 要仿造既有流程時，需要的正是這一包。

**唯讀**：一律經 `bpm_kb.db.Database`（`readonly=True`）與參數化查詢，
不重寫任何關聯查詢（AGENTS.md 7.5），也不呼叫 SOAP —— 190 正式區的 API 禁令不變。

    python 8_BPMAIworker/tools/fetch_online.py --list --keyword MIS --host 190
    python 8_BPMAIworker/tools/fetch_online.py --process SIC005 --host 190

產出（預設寫到 `8_BPMAIworker/out/<host>_<流程ID>_v<版本>/`，該目錄不進版控）：

    流程/<流程ID>_v<n>.bpmn          ProcessDefinition.bpmXML 原文（只有畫布座標）
    流程/流程結構.json                關卡、連線、執行者、各關卡欄位權限
    表單/<表單ID>_v<n>.form           FormDefinition.defSerialize 原文
    表單/<表單ID>_v<n>.欄位.json      用 1_xml_tool/core 反解出來的欄位清單
    腳本/<表單ID>_v<n>.js             FormDefinition.script（桌機版表單 JavaScript）
    腳本/<表單ID>_v<n>.mobile.js      FormDefinition.mobileScript
    腳本/<表單ID>_v<n>.腳本盤點.md    舊寫法盤點，給後續優化當清單
    摘要.md                           這一包有什麼、版面是絕對位置還是響應式
"""

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '1_xml_tool'))
sys.path.insert(0, os.path.join(ROOT, '3_db_explorer'))

from core import form_handler                          # noqa: E402
from bpm_kb import config, extract, process_graph      # noqa: E402
from bpm_kb.db import Database, big_text               # noqa: E402

OUT_ROOT = os.path.abspath(os.path.join(HERE, '..', 'out'))

# 可連的主機。與 4_db_viewer/backend/app/settings.py 的清單一致。
# 190 正式區只能 SELECT（AGENTS.md 8.2），SOAP 一律不連（8.1）。
HOSTS = {
    '191': ('BPM 191 測試區', '10.10.130.191', False),
    '190': ('BPM 190 正式區', '10.10.130.190', True),
}

# 主旨範本的表單參照：<#表單ID~~欄位ID>（AGENTS.md 7.1 的次來源）
SUBJECT_REF = re.compile(r'<#([\w.\-]+)~~')

SAFE_NAME = re.compile(r'[^A-Za-z0-9_\-]+')

# 鼎新表單的五個生命週期函式（見 docs/表單腳本手冊.md 第 1 節）
LIFECYCLE = ('formCreate', 'formOpen', 'formSave', 'formClose', 'formDispatch')

FUNCTION_RE = re.compile(r'^\s*function\s+([A-Za-z_$][\w$]*)\s*\(', re.M)

# 舊寫法盤點規則：(正規式, 標題, 為什麼要改)
# 只列「看得到就一定是問題」的，猜測性的不列 —— 盤點表要能直接當工單用。
SCRIPT_RULES = [
    # document.write 載 ../../CustomJsLib/ 是鼎新自己的標準寫法
    # （見 BPM5892/BPM_表單腳本可用資源.md），不算舊寫法；載別的地方才要看。
    (re.compile(r'document\.write\s*\((?!.*\.\./\.\./CustomJsLib/)'),
     'document.write 載入 CustomJsLib 以外的來源',
     '外部來源掛掉整張表單就開不起來；確認這支 JS 真的有在用，沒用就刪。'),
    (re.compile(r'https?://\d{1,3}(?:\.\d{1,3}){3}'),
     '硬編 IP 位址',
     '換主機或改走 HTTPS 就會壞；改成相對路徑。'),
    (re.compile(r'\.query\s*\(\s*[A-Za-z_$][\w$]*\s*\)'),
     'DataSource.query 吃的是串接出來的 SQL',
     '欄位值直接進 SQL，一個單引號就能改變語意；至少要先過濾，或改走後端服務。'),
    (re.compile(r'\bdocument\.all\b'),
     'IE 專屬 document.all',
     '改 document.getElementById。'),
    (re.compile(r'\battachEvent\s*\(|\bwindow\.event\b'),
     'IE 專屬事件 API',
     '改 addEventListener 與事件參數。'),
    (re.compile(r'new\s+ActiveXObject'),
     'ActiveXObject',
     'IE 專屬，現代瀏覽器直接丟例外。'),
    (re.compile(r'(?<![\w.$])eval\s*\('),
     'eval',
     '多半可用物件查表或 JSON.parse 取代。'),
    (re.compile(r'\balert\s*\('),
     'alert 阻斷式提示',
     '手機版會卡住流程；能用欄位提示就不要用 alert。'),
    (re.compile(r'setTimeout\s*\(\s*[\'"]'),
     'setTimeout 傳字串',
     '等同 eval；改傳函式。'),
    (re.compile(r'==\s*[\'"]null[\'"]|[\'"]null[\'"]\s*=='),
     '拿字串 "null" 當空值判斷',
     '資料來源回的是真 null 還是字串 "null" 要先確認，兩者混用遲早判錯。'),
]

# 這幾種寫法常常成組出現，是「把欄位改成唯讀灰底」的舊寫法
READONLY_TRIPLE = re.compile(
    r'getElementById\(\s*[\'"]([\w$]+)[\'"]\s*\)\.'
    r'(?:disabled|readOnly|style\.backgroundColor)')


def _safe(name):
    return SAFE_NAME.sub('_', (name or 'unnamed').strip())[:80]


def _write(path, text):
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text or '')
    return path


def db_settings(host):
    """套上指定主機的位址；正式區可用 BPM_DB_USER_190 之類的環境變數覆寫帳密。"""
    label, address, production = HOSTS[host]
    values = dict(config.load())
    values['BPM_DB_HOST'] = address
    for field in ('BPM_DB_USER', 'BPM_DB_PASSWORD', 'BPM_DB_NAME'):
        override = os.environ.get('%s_%s' % (field, host))
        if override:
            values[field] = override
    return values, label, production


# ---------------------------------------------------------------- 查詢

def _exact(rows, wanted):
    """bpm_kb 的 keyword 是 LIKE，這裡收斂成精確比對。

    線上真的有 SIC005（MIS問題反應單）與 SIC005_（ERP開帳申請單）並存，
    模糊比對會抓錯單。
    """
    return [r for r in rows if (r.get('id') or '').strip() == wanted]


def _pick_version(rows, version):
    """挑版本：指定就照指定，沒指定取已發佈的最大版；都沒發佈就取最大版並回報。"""
    if not rows:
        return None, ''
    if version:
        hit = [r for r in rows if (r.get('version') or 0) == version]
        return (hit[0] if hit else None), ''
    released = [r for r in rows if (r.get('publicationStatus') or '') == 'RELEASED']
    if released:
        return max(released, key=lambda r: r.get('version') or 0), ''
    newest = max(rows, key=lambda r: r.get('version') or 0)
    return newest, '沒有任何 RELEASED 版本，取的是 v%s（%s）' % (
        newest.get('version'), newest.get('publicationStatus'))


def fetch_subject_templet(database, package_oid):
    """主旨範本，用來補流程與表單的次要關聯（AGENTS.md 7.1）。"""
    rows = database.query(
        'SELECT %s AS t FROM ProcessPackage WHERE OID = ?' % big_text('subjectTemplet'),
        (package_oid,))
    return rows[0]['t'] if rows else ''


# ---------------------------------------------------------------- 腳本盤點

def audit_script(text, form_id):
    """盤點一份表單 JavaScript 的舊寫法，回傳 (統計, markdown)。

    只報「數得出來」的事實，不做風格評分 —— 這張表是給人決定要不要改的。
    """
    lines = (text or '').splitlines()
    functions = FUNCTION_RE.findall(text or '')
    commented = sum(1 for ln in lines if re.match(r'\s*//\s*\S', ln))

    hits = []
    for pattern, title, why in SCRIPT_RULES:
        found = [(i + 1, ln.strip()) for i, ln in enumerate(lines) if pattern.search(ln)]
        if found:
            hits.append((title, why, found))

    readonly_fields = {}
    for field_id in READONLY_TRIPLE.findall(text or ''):
        readonly_fields[field_id] = readonly_fields.get(field_id, 0) + 1
    repeated = sorted([(n, f) for f, n in readonly_fields.items() if n >= 2], reverse=True)

    stats = {
        'lines': len(lines),
        'functions': len(functions),
        'getElementById': len(re.findall(r'getElementById\s*\(', text or '')),
        'commentedLines': commented,
        'missingLifecycle': [n for n in LIFECYCLE if n not in functions],
        'issues': len(hits),
    }

    out = ['# %s 腳本盤點' % form_id, '',
           '共 %d 行、%d 個函式、%d 次 getElementById、%d 行是被註解掉的內容。'
           % (stats['lines'], stats['functions'], stats['getElementById'], commented), '',
           '## 生命週期函式', '']
    for name in LIFECYCLE:
        out.append('- %s %s' % ('[有]' if name in functions else '[無]', name))

    custom = [f for f in functions if f not in LIFECYCLE]
    out += ['', '## 自訂函式（%d 個）' % len(custom), '']
    out += ['- `%s()`' % name for name in custom]

    out += ['', '## 舊寫法（%d 類）' % len(hits), '']
    if not hits:
        out.append('沒有命中任何盤點規則。**這不代表沒有問題**，只代表規則沒涵蓋到。')
    for title, why, found in hits:
        out += ['### %s —— %d 處' % (title, len(found)), '', why, '']
        for line_no, content in found[:8]:
            out.append('- 第 %d 行：`%s`' % (line_no, content[:120]))
        if len(found) > 8:
            out.append('- （其餘 %d 處略）' % (len(found) - 8))
        out.append('')

    if repeated:
        out += ['## 重複的欄位唯讀設定', '',
                '同一個欄位被反覆設定 disabled / readOnly / backgroundColor，可收成一個 helper：', '']
        for count, field_id in repeated[:20]:
            out.append('- `%s` —— %d 次' % (field_id, count))
        out.append('')

    return stats, '\n'.join(out) + '\n'


# ---------------------------------------------------------------- 落地

def dump_form(database, row, out_dir):
    """把一個表單版本的 defSerialize / script / mobileScript / rwdLayout 全部落地。"""
    form_id = (row.get('id') or '').strip()
    stem = '%s_v%s' % (_safe(form_id), row.get('version'))
    result = {'formId': form_id, 'version': row.get('version'),
              'formName': (row.get('formDefinitionName') or '').strip(),
              'publicationStatus': (row.get('publicationStatus') or '').strip(),
              'files': {}}

    xml = extract.fetch_form_xml(database, row['OID'])
    result['files']['form'] = _write(os.path.join(out_dir, '表單', stem + '.form'), xml)

    fields = form_handler.extract_text(xml, stem) if xml else {}
    result['fieldCount'] = len(fields.get('fields', []))
    # 給 process_graph 判斷 orphaned 與按鈕用，格式同 extract.form_index
    result['fieldIndex'] = {f['id']: {'name': f['name'], 'type': f['type']}
                            for f in fields.get('fields', []) if f.get('id')}
    result['files']['fields'] = _write(
        os.path.join(out_dir, '表單', stem + '.欄位.json'),
        json.dumps(fields, ensure_ascii=False, indent=2, default=str))

    extras = extract.fetch_form_extras(database, row['OID'])
    script = extras.get('script') or ''
    mobile = extras.get('mobileScript') or ''
    rwd = extras.get('rwdLayout') or ''

    result['files']['script'] = _write(os.path.join(out_dir, '腳本', stem + '.js'), script)
    result['scriptChars'] = len(script)
    if mobile:
        result['files']['mobileScript'] = _write(
            os.path.join(out_dir, '腳本', stem + '.mobile.js'), mobile)
    result['mobileScriptChars'] = len(mobile)

    # rwdLayout 有值＝響應式格線版面；空值＝絕對位置（座標寫在元件的 elementStyles）
    result['layout'] = 'RWD' if rwd.strip() else 'ABSOLUTE'
    if rwd.strip():
        result['files']['rwdLayout'] = _write(
            os.path.join(out_dir, '表單', stem + '.rwdLayout.json'), rwd)

    if script:
        stats, report = audit_script(script, form_id)
        result['scriptAudit'] = stats
        result['files']['scriptAudit'] = _write(
            os.path.join(out_dir, '腳本', stem + '.腳本盤點.md'), report)
    return result


def _permission_items(activity):
    return list(activity.get('fieldPermissions', [])) + list(activity.get('buttons', []))


def _orphan_count(activity):
    """權限清單裡有、但表單定義中不存在的元件數（AGENTS.md 第 6 節要求標出來）。"""
    return len([item for item in _permission_items(activity) if item.get('orphaned')])


def summary_markdown(host, label, package, graph, forms, missing_forms, subject):
    """給人看的一頁摘要：這包有什麼、哪裡對不起來。"""
    lines = ['# %s / %s v%s（%s）' % (label, graph.get('processId'),
                                     graph.get('version'), graph.get('processName')), '',
             '- 來源主機：%s（%s）' % (label, HOSTS[host][1]),
             '- 流程套件 OID：%s' % package.get('OID'),
             '- ProcessDefinition OID：%s' % package.get('processDefinitionOID'),
             '- 發佈狀態：%s，流程型態：%s' % (graph.get('publicationStatus'),
                                              graph.get('flowType')),
             '- 建立時間：%s' % package.get('createdTime'), '',
             '## 關卡', '',
             '| 關卡 ID | 名稱 | BPMN 型別 | 執行方式 | 表單 | 權限欄位 | 對不到表單 |',
             '|:---|:---|:---|:---|:---|---:|---:|']
    known = set(f['formId'] for f in forms)
    for activity in process_graph.order_activities(graph):
        form_id = activity['formId']
        # 表單本身查不到時，orphaned 一律是 False（沒有東西可比對），不能報 0
        orphan = '全部' if (form_id and form_id not in known) else _orphan_count(activity)
        lines.append('| %s | %s | %s | %s | %s | %d | %s |' % (
            activity['id'], activity['name'] or '—', activity['bpmnType'],
            activity['performType'], form_id or '—',
            len(_permission_items(activity)), orphan))

    lines += ['', '## 表單', '',
              '| 表單 ID | 名稱 | 版本 | 狀態 | 欄位數 | 版面 | script | mobileScript |',
              '|:---|:---|---:|:---|---:|:---|---:|---:|']
    for form in forms:
        lines.append('| %s | %s | v%s | %s | %d | %s | %d 字 | %d 字 |' % (
            form['formId'], form['formName'], form['version'], form['publicationStatus'],
            form['fieldCount'],
            '絕對位置' if form['layout'] == 'ABSOLUTE' else '響應式',
            form['scriptChars'], form['mobileScriptChars']))

    if missing_forms:
        lines += ['', '## 查不到定義的表單參照 ⚠️', '',
                  '關卡權限或主旨範本指到這些表單 ID，但 FormDefinition 裡沒有：', '']
        for form_id, where in missing_forms:
            lines.append('- `%s`（來自 %s）' % (form_id, where))
        lines += ['',
                  '這代表流程版本與表單版本脫節，或是複製流程時把別支流程的權限一起帶過來。'
                  '不要自行猜哪個才對，要人工確認。']

    orphan_rows = [(a['id'], a['formId'],
                    [i['id'] for i in _permission_items(a) if i.get('orphaned')])
                   for a in process_graph.order_activities(graph) if _orphan_count(a)]
    if orphan_rows:
        lines += ['', '## 對不到表單元件的權限欄位 ⚠️', '',
                  '關卡設了這些欄位的權限，但表單的最新已發佈版沒有這個元件 —— '
                  '代表流程版本與表單版本脫節。仿造時不要照抄這些欄位。', '']
        for activity_id, form_id, ids in orphan_rows:
            lines.append('- `%s`（表單 %s，%d 個）：%s'
                         % (activity_id, form_id or '—', len(ids), '、'.join(ids)))

    if subject:
        lines += ['', '## 主旨範本', '', '```', subject, '```']

    lines += ['', '## 版面模式怎麼判定', '',
              '`FormDefinition.rwdLayout` 有值＝響應式格線版面；空值＝絕對位置，'
              '座標寫在各元件的 `elementStyles` 裡。舊表單多半是絕對位置。']
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- 指令

def cmd_list(database, keyword):
    processes = extract.list_processes(database, keyword=keyword, latest_only=True)
    forms = extract.list_forms(database, keyword=keyword, latest_only=True)
    print('流程（%d 支）' % len(processes))
    for row in processes:
        print('  %-30s v%-4s %-14s %s' % ((row.get('id') or '').strip(),
                                          row.get('version'),
                                          row.get('publicationStatus'),
                                          (row.get('processPackageName') or '').strip()))
    print('表單（%d 張）' % len(forms))
    for row in forms:
        print('  %-30s v%-4s %-14s %s' % ((row.get('id') or '').strip(),
                                          row.get('version'),
                                          row.get('publicationStatus'),
                                          (row.get('formDefinitionName') or '').strip()))
    return 0


def _wanted_forms(graph, subject, extra):
    """表單來源有三處，全部收進來再去重（AGENTS.md 7.1：只查一處會漏）。"""
    wanted, seen = [], set()
    for activity in graph.get('activities', []):
        form_id = activity.get('formId')
        if form_id and form_id not in seen:
            seen.add(form_id)
            wanted.append((form_id, '關卡 %s 的欄位權限' % activity['id']))
    for form_id in SUBJECT_REF.findall(subject or ''):
        if form_id not in seen:
            seen.add(form_id)
            wanted.append((form_id, '主旨範本'))
    for form_id in (extra or []):
        if form_id not in seen:
            seen.add(form_id)
            wanted.append((form_id, '--form 指定'))
    return wanted


def cmd_fetch(database, args, out_root):
    rows = _exact(extract.list_processes(database, keyword=args.process), args.process)
    if not rows:
        print('找不到流程 ID：%s（精確比對，不是模糊搜尋）' % args.process)
        return 1
    package, note = _pick_version(rows, args.version)
    if package is None:
        print('流程 %s 沒有 v%s 這一版' % (args.process, args.version))
        return 1
    if note:
        print('注意：%s' % note)

    label = HOSTS[args.host][0]
    out_dir = os.path.join(out_root, '%s_%s_v%s' % (args.host, _safe(args.process),
                                                    package.get('version')))
    print('抓取 %s / %s v%s → %s' % (label, args.process, package.get('version'), out_dir))

    graph = process_graph.build(database, package)
    if not graph:
        print('流程 %s v%s 查不到 ProcessDefinition，無法組出關卡結構'
              % (args.process, package.get('version')))
        return 1

    stem = '%s_v%s' % (_safe(args.process), package.get('version'))
    bpm_xml = extract.fetch_process_xml(database, package['processDefinitionOID'])
    _write(os.path.join(out_dir, '流程', stem + '.bpmn'), bpm_xml)

    subject = fetch_subject_templet(database, package['OID'])

    forms, missing, form_index = [], [], {}
    for form_id, where in _wanted_forms(graph, subject, args.form):
        candidates = _exact(extract.list_forms(database, keyword=form_id), form_id)
        if not candidates:
            missing.append((form_id, where))
            print('  [缺] 表單 %s —— %s 指到它，但 FormDefinition 裡沒有' % (form_id, where))
            continue
        row, form_note = _pick_version(candidates, None)
        if form_note:
            print('  [注意] 表單 %s：%s' % (form_id, form_note))
        info = dump_form(database, row, out_dir)
        forms.append(info)
        form_index[info['formId']] = info.pop('fieldIndex')
        print('  [取] 表單 %s v%s：%d 欄位、%s版面、script %d 字'
              % (info['formId'], info['version'], info['fieldCount'],
                 '絕對位置' if info['layout'] == 'ABSOLUTE' else '響應式',
                 info['scriptChars']))

    # 表單抓完才知道每張表單有哪些元件，所以組第二次 —— 這次帶 form_index，
    # process_graph 才標得出 orphaned（權限裡有、表單裡沒有的欄位）。
    graph = process_graph.build(database, package, form_index)
    _write(os.path.join(out_dir, '流程', '流程結構.json'),
           json.dumps(graph, ensure_ascii=False, indent=2, default=str))

    _write(os.path.join(out_dir, '摘要.md'),
           summary_markdown(args.host, label, package, graph, forms, missing, subject))

    orphans = sum(_orphan_count(a) for a in graph.get('activities', []))
    print('完成。%d 關卡、%d 張表單、%d 個查不到的表單參照、%d 個對不到表單元件的權限欄位。'
          % (len(graph.get('activities', [])), len(forms), len(missing), orphans))
    print('摘要：%s' % os.path.join(out_dir, '摘要.md'))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='從線上 BPM 資料庫唯讀抓取流程、表單與表單 JavaScript')
    parser.add_argument('--host', default='191', choices=sorted(HOSTS),
                        help='191 測試區（預設）或 190 正式區；190 只做 SELECT')
    parser.add_argument('--process', help='流程 ID（精確比對）')
    parser.add_argument('--form', action='append', help='額外要抓的表單 ID，可重複')
    parser.add_argument('--version', type=int, help='流程版本，預設取已發佈的最新版')
    parser.add_argument('--list', action='store_true', help='只列出符合關鍵字的流程與表單')
    parser.add_argument('--keyword', default='', help='--list 的搜尋關鍵字（模糊比對）')
    parser.add_argument('--out', default=OUT_ROOT, help='輸出根目錄')
    args = parser.parse_args(argv)

    if not args.list and not args.process:
        parser.error('要嘛給 --process，要嘛用 --list 先找')

    settings, label, production = db_settings(args.host)
    print('連線 %s：%s（唯讀）' % (label, config.describe(settings)))
    if production:
        print('※ 正式區只做 SELECT，本工具不寫入、不呼叫 SOAP。')

    with Database(settings) as database:
        if args.list:
            return cmd_list(database, args.keyword)
        return cmd_fetch(database, args, os.path.abspath(args.out))


if __name__ == '__main__':
    sys.exit(main())
