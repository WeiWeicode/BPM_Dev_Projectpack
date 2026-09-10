# -*- coding: utf-8 -*-
"""對產出的 .form / .bpmn 跑靜態檢查與反解對比（見 ../docs/驗證與驗收.md 的 V2、V4）。

檢查不到的一律說檢查不到，不假裝通過。匯入設計師與實跑（V5）本工具做不到。

執行：python 8_BPMAIworker/tools/verify.py
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '1_xml_tool'))
sys.path.insert(0, HERE)

from core import xml_utils as X          # noqa: E402
from core import form_handler            # noqa: E402
from core import bpmn_handler            # noqa: E402
import xstream_ref                       # noqa: E402

PROJ = os.path.join(ROOT, 'samples', 'AI設計的流程測試')
FORM = os.path.join(PROJ, '表單', 'AIDesignTestForm.form')
BPMN = os.path.join(PROJ, '流程', 'AI設計的流程測試.bpmn')

_fail = []
_warn = []


def ok(cond, msg, detail=''):
    if cond:
        print('  [通過] %s' % msg)
    else:
        print('  [失敗] %s%s' % (msg, ('　→ ' + detail) if detail else ''))
        _fail.append(msg)


def warn(msg):
    print('  [注意] %s' % msg)
    _warn.append(msg)


def _wellformed(path):
    """只用 ElementTree 做「讀得起來嗎」的檢查，絕不用它輸出（會破壞 XStream 格式）。"""
    try:
        ET.parse(path)
        return True, ''
    except Exception as exc:
        return False, str(exc)


def check_form():
    print('== .form 靜態檢查 ==')
    text, _ = X.read_xml(FORM)

    good, err = _wellformed(FORM)
    ok(good, 'XML 本身合法', err)

    ids = [int(x) for x in re.findall(r'\sid="(\d+)"', text)]
    ok(ids == list(range(1, len(ids) + 1)),
       'XStream id 為 1…%d 嚴格連號' % len(ids))
    ok('reference="' not in text, '已無任何 reference（增刪元件後不會指錯）')

    el_ids = set()
    dup = []
    for s in X.find_blocks(text, lambda n: n.startswith('com.dsc.nana.domain.form.')
                           and n.endswith('ElementDefinition')):
        eid = X.child_text(text, s, 'id')
        if eid in el_ids:
            dup.append(eid)
        el_ids.add(eid)
    ok(not dup, '元件 ID 無重複', '、'.join(dup))

    bad = [i for i in el_ids if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', i)]
    ok(not bad, '元件 ID 皆為合法的 XML 標籤名', '、'.join(bad))

    rl = X.find_blocks(text, lambda n: n == 'rwdLayout')[0]
    layout = json.loads(X.xml_unescape(text[rl.inner_start:rl.inner_end]))
    lay_ids = set(re.findall(r'"id":\s*"([^"]+)"',
                             json.dumps(layout, ensure_ascii=False)))
    lay_ids -= {'SubTab22_0', 'SubTab22_1'}          # 頁籤子項不是元件
    missing = sorted(lay_ids - el_ids)
    ok(not missing, '版面（rwdLayout）引用的元件都存在',
       '、'.join(missing) + '（會讓設計器丟 Cannot read properties of null）')

    js, _msg = form_handler.extract_script(FORM)
    ok(js is not None and 'formOpen' in js, '腳本可反轉義且含生命週期函式')
    ok(js.count('{') == js.count('}'), '腳本大括號配對')

    d = form_handler.extract(FORM)
    print('  表單 ID=%s／名稱=%s／可辨識元件 %d 個'
          % (d['formId'], d['formName'], len(d['fields'])))
    return d, el_ids


def check_bpmn(form_field_ids):
    print()
    print('== .bpmn 靜態檢查 ==')
    text, _ = X.read_xml(BPMN)
    ns = 'com.dsc.nana.domain.workflow__definition.'

    good, err = _wellformed(BPMN)
    ok(good, 'XML 本身合法', err)

    _root, nodes = xstream_ref.build(text)
    unresolved = [(n.name, n.ref) for n in nodes
                  if n.ref and xstream_ref.resolve(n, n.ref) is None]
    ok(not unresolved, '所有 reference 都解析得到目標', str(unresolved[:3]))

    oids = re.findall(r'<(?:OID|containerOID)>([0-9a-f]{32})</', text)
    d = bpmn_handler.extract(BPMN)
    acts = {a['id']: a for a in d['activities']}
    print('  流程 ID=%s／名稱=%s／關卡 %d 個'
          % (d['processId'], d['processName'], len(acts)))

    trans = []
    for s in X.find_blocks(text, lambda n: n == ns + 'TransitionDefinition'):
        trans.append((X.child_text(text, s, 'fromActivityDefinitionId'),
                      X.child_text(text, s, 'toActivityDefinitionId')))
    dangling = [t for t in trans if t[0] not in acts or t[1] not in acts]
    ok(not dangling, '連線兩端的關卡都存在', str(dangling))

    starts = [a for a in d['activities'] if a['type'] == 'StartEvent']
    ends = [a for a in d['activities'] if a['type'] == 'EndEvent']
    ok(len(starts) == 1, '恰好一個起點', '目前 %d 個' % len(starts))
    ok(len(ends) >= 1, '至少一個終點')

    # 從起點走得到所有關卡嗎
    nxt = {}
    for f, t in trans:
        nxt.setdefault(f, []).append(t)
    seen, stack = set(), [starts[0]['id']] if starts else []
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(nxt.get(cur, []))
    ok(seen == set(acts), '所有關卡都從起點連得到',
       '孤立：' + '、'.join(sorted(set(acts) - seen)))

    # 執行者
    parts = set()
    for s in X.find_blocks(text, lambda n: n == ns + 'ParticipantDefinition'):
        parts.add(X.child_text(text, s, 'id'))
    miss_perf = []
    for s in X.find_blocks(text, lambda n: n == ns + 'ActivityDefinition'):
        pid = X.child_text(text, s, 'performerIds').strip()
        if pid and pid not in parts:
            miss_perf.append((X.child_text(text, s, 'id'), pid))
    ok(not miss_perf, '關卡指定的執行者都還在', str(miss_perf))

    # bpmXML 與關卡集合一致
    span = X.find_blocks(text, lambda n: n == 'bpmXML')[0]
    diagram = X.xml_unescape(text[span.inner_start:span.inner_end])
    node_ids = set(re.findall(r'<Node ClassName="(?!DiagramLink)[^"]+" Id="([^"]+)"', diagram))
    ok(node_ids == set(acts), '流程圖節點與關卡一一對應',
       '圖多：%s／圖少：%s' % (sorted(node_ids - set(acts)), sorted(set(acts) - node_ids)))
    link_ids = set(re.findall(r'<Node ClassName="DiagramLink" Id="([^"]+)"', diagram))
    ok(len(link_ids) == len(trans), '流程圖連線數與 TransitionDefinition 數相同',
       '圖 %d 條 / 定義 %d 條' % (len(link_ids), len(trans)))

    # 權限
    bad_fields = []
    total = 0
    for a in d['activities']:
        for item in a.get('buttons', []) + a.get('fieldPermissions', []):
            total += 1
            if item['permission'] not in ('ENABLED', 'INVISIBLE', 'FULL_CONTROL'):
                bad_fields.append((a['id'], item['id'], item['permission']))
            if item['id'] not in form_field_ids:
                bad_fields.append((a['id'], item['id'], '表單裡沒有這個欄位'))
    ok(not bad_fields, '權限項目的欄位都存在且值合法（共 %d 項）' % total, str(bad_fields[:5]))

    form_ids = set(a.get('formId') for a in d['activities'] if a.get('formId'))
    ok(form_ids <= {'AIDesignTestForm'}, '權限字串綁的表單 ID 正確', str(form_ids))

    own = re.findall(r'<OID>([0-9a-f]{32})</OID>', text)
    ok(len(set(own)) == len(own), '每個物件自己的 <OID> 互不重複（共 %d 個）' % len(own),
       '重複：%s' % [o for o in set(own) if own.count(o) > 1][:3])
    print('  containerOID 另有 %d 處（本來就會重複指向同一個容器）'
          % (len(oids) - len(own)))

    # 關卡開表單靠 relevantDataDefinitionId，指錯就開不出表單
    rd_ids = set()
    for s in X.find_blocks(text, lambda n: n == ns + 'RelevantDataDefinition'):
        rd_ids.add(X.child_text(text, s, 'id'))
    refs = set(re.findall(r'<relevantDataDefinitionId>([^<]*)</relevantDataDefinitionId>', text))
    ok(refs <= rd_ids, '關卡引用的流程變數都存在', '缺：%s' % sorted(refs - rd_ids))
    ok('AIDesignTestForm' in rd_ids, '流程變數含表單 AIDesignTestForm')

    for a in d['activities']:
        if a['type'] in ('UserTask', 'ManualTask'):
            print('    %-18s %-8s 按鈕 %d／欄位 %d'
                  % (a['id'], a['name'], len(a['buttons']), len(a['fieldPermissions'])))
    return d


def main():
    d_form, el_ids = check_form()
    d_proc = check_bpmn(el_ids)

    print()
    print('== 結論 ==')
    if _fail:
        print('  V2／V4 有 %d 項未通過：' % len(_fail))
        for f in _fail:
            print('    - ' + f)
    else:
        print('  V2（靜態 lint）與 V4（反解對比）全部通過。')
    print('  V5（匯入鼎新設計師、實際跑完一張單）本工具做不到，尚未執行。')
    return 1 if _fail else 0


if __name__ == '__main__':
    sys.exit(main())
