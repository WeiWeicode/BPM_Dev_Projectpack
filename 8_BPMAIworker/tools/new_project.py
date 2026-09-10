# -*- coding: utf-8 -*-
"""從空白範本複製出一個新專案（.form + .bpmn + .js）。

範本：`8_BPMAIworker/templates/原始空白專案/`
      —— 由鼎新設計器直接匯出的空白專案，是目前最乾淨的基底。

複製時只換掉「識別身分」的那幾格：表單 ID／流程 ID／中文名／關卡 ID／OID。
元件與欄位權限一律留空，交給後續步驟（build_form.py、set_permissions.py）。

    python 8_BPMAIworker/tools/new_project.py --name 採購申請單 \\
        --form-id PurchaseForm --process-id PurchaseProcess

產出：samples/<name>/表單/<form-id>.form、.js
      samples/<name>/流程/<name>.bpmn
      samples/<name>/project.json
"""

import argparse
import hashlib
import io
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
from core import bpmn_handler            # noqa: E402
from core import form_handler            # noqa: E402
import bpm_edit                          # noqa: E402
import xstream_ref                       # noqa: E402

TPL_DIR = os.path.join(HERE, '..', 'templates', '原始空白專案')
TPL_FORM = os.path.join(TPL_DIR, '表單', 'OriginalBlankFormProject.form')
TPL_BPMN = os.path.join(TPL_DIR, '流程', 'OriginalBlankProcessProject.bpmn')

# 範本裡的識別字，複製時全部要換掉
TPL_FORM_ID = 'OriginalBlankFormProject'
TPL_PROCESS_ID = 'OriginalBlankProcessProject'
TPL_PROCESS_NAME = '原始空白流程專案'
TPL_APPLY_ACT = 'UserTask_3'          # 執行者已是 PROCESS_REQUESTER
TPL_MANAGER_ACT = 'UserTask_4'        # 執行者已是 MANAGER

# 本工具自己的 OID 後綴（24 碼）。前 8 碼依專案名稱分段，避免兩個專案撞號。
OID_SUFFIX = 'a1de51000851cac97a977dbb'

ID_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _oid_base(seed):
    """依專案名稱決定 OID 前綴的起算值，每個專案配 256 個號。"""
    h = int(hashlib.md5(seed.encode('utf-8')).hexdigest()[:4], 16)
    return 0x7a100000 + h * 0x100


def _check_id(label, value):
    if not ID_RE.match(value or ''):
        raise SystemExit('%s「%s」不合法：只允許英數字與底線、不可數字開頭。\n'
                         '（這些 ID 會被當成 XML 標籤名寫進欄位權限字串）'
                         % (label, value))


def build_form(args, oid_base):
    text, bom = X.read_xml(TPL_FORM)

    text, n = bpm_edit.replace_leaf(text, 'id', TPL_FORM_ID, args.form_id)
    if n != 1:
        raise SystemExit('範本的表單 <id> 應該只有 1 處，實際 %d 處' % n)
    text, n = bpm_edit.replace_leaf(text, 'name', TPL_FORM_ID, X.xml_escape(args.name))
    if n != 1:
        raise SystemExit('範本的表單 <name> 應該只有 1 處，實際 %d 處' % n)

    text, n_oid = bpm_edit.remap_oids(text, oid_base, OID_SUFFIX)

    out = os.path.join(args.out, '表單', args.form_id + '.form')
    X.write_xml(out, text, bom)

    # 把生命週期骨架另存成 .js，之後改腳本改這一份就好
    js, _msg = form_handler.extract_script(out)
    js_path = os.path.join(args.out, '表單', args.form_id + '.js')
    io.open(js_path, 'w', encoding='utf-8', newline='').write(js)

    print('  表單 %s（換掉 %d 個 OID，腳本另存 %s）'
          % (os.path.basename(out), n_oid, os.path.basename(js_path)))
    return out


def build_bpmn(args, oid_base):
    text, bom = X.read_xml(TPL_BPMN)

    # 流程包 / 流程定義
    text, n1 = bpm_edit.replace_leaf(text, 'id', TPL_PROCESS_ID, args.process_id)
    text, n2 = bpm_edit.replace_leaf(text, 'mainProcessDefinitionId',
                                     TPL_PROCESS_ID, args.process_id)
    text, n3 = bpm_edit.replace_leaf(text, 'name', TPL_PROCESS_NAME, X.xml_escape(args.name))
    if (n1, n2, n3) != (2, 1, 2):
        raise SystemExit('流程識別字的處數與預期不符（id=%d, main=%d, name=%d）' % (n1, n2, n3))

    # 表單繫結：關卡是靠 relevantDataDefinitionId 找到表單的，四處都要換
    total = 0
    for tag in ('formDefinitionId', 'relevantDataDefinitionId', 'id', 'name'):
        text, n = bpm_edit.replace_leaf(text, tag, TPL_FORM_ID,
                                        X.xml_escape(args.name) if tag == 'name' else args.form_id)
        total += n
    if total != 4:
        raise SystemExit('表單繫結參照應為 4 處，實際 %d 處' % total)

    # 關卡改名（連動流程圖節點、連線、參與者參照）
    tmp = os.path.join(args.out, '流程', '_tmp.bpmn')
    if not os.path.isdir(os.path.dirname(tmp)):
        os.makedirs(os.path.dirname(tmp))
    X.write_xml(tmp, text, bom)
    cfg = {'activities': [
        {'originalId': TPL_APPLY_ACT, 'id': args.apply_id, 'name': args.apply_name,
         'buttons': [], 'fieldPermissions': []},
        {'originalId': TPL_MANAGER_ACT, 'id': args.manager_id, 'name': args.manager_name,
         'buttons': [], 'fieldPermissions': []},
    ]}
    acts, _f, msgs = bpmn_handler.write_back(tmp, cfg, tmp)
    text, bom = X.read_xml(tmp)
    os.remove(tmp)

    # write_back 只改 ID，中文名要自己寫
    for act_id, act_name in ((args.apply_id, args.apply_name),
                             (args.manager_id, args.manager_name)):
        s = bpm_edit.find_by_child_id(text, bpm_edit.WF_NS + 'ActivityDefinition', act_id)
        text = bpm_edit.set_child(text, s, 'name', X.xml_escape(act_name))

    # 流程圖上的節點文字：一定要認 Node 的 Id 再改，
    # 兩個 UserTask 的預設文字都是「人員任務」，照出現順序改會張冠李戴
    span = X.find_blocks(text, lambda n: n == 'bpmXML')[0]
    diagram = X.xml_unescape(text[span.inner_start:span.inner_end])
    for act_id, act_name in ((args.apply_id, args.apply_name),
                             (args.manager_id, args.manager_name)):
        pat = re.compile(r'(<Node ClassName="UserTask" Id="%s">.*?<Text>)[^<]*(</Text>)'
                         % re.escape(act_id), re.S)
        diagram, n = pat.subn(lambda m: m.group(1) + act_name + m.group(2), diagram, count=1)
        if n != 1:
            raise SystemExit('流程圖上找不到關卡節點 %s' % act_id)
    text = X.apply_edits(text, [(span.inner_start, span.inner_end,
                                 X.xml_escape(diagram))])

    text, n_oid = bpm_edit.remap_oids(text, oid_base + 0x80, OID_SUFFIX)

    out = os.path.join(args.out, '流程', args.name + '.bpmn')
    X.write_xml(out, text, bom)
    print('  流程 %s（改名 %d 個關卡，換掉 %d 個 OID）'
          % (os.path.basename(out), acts, n_oid))
    for m in msgs:
        print('   ' + m)
    return out


def check(form_path, bpmn_path, args):
    print()
    print('== 複製後檢查 ==')
    bad = 0

    for p in (form_path, bpmn_path):
        try:
            ET.parse(p)
            print('  [通過] XML 合法：%s' % os.path.basename(p))
        except Exception as exc:
            print('  [失敗] XML 不合法：%s → %s' % (os.path.basename(p), exc))
            bad += 1

    for p in (form_path, bpmn_path):
        t, _ = X.read_xml(p)
        left = [k for k in (TPL_FORM_ID, TPL_PROCESS_ID, TPL_PROCESS_NAME,
                            TPL_APPLY_ACT, TPL_MANAGER_ACT) if k in t]
        if left:
            print('  [失敗] %s 仍殘留範本識別字：%s' % (os.path.basename(p), '、'.join(left)))
            bad += 1
        else:
            print('  [通過] %s 已無範本識別字' % os.path.basename(p))

    t, _ = X.read_xml(bpmn_path)
    _root, nodes = xstream_ref.build(t)
    unresolved = [(n.name, n.ref) for n in nodes
                  if n.ref and xstream_ref.resolve(n, n.ref) is None]
    if unresolved:
        print('  [失敗] 有 %d 處 reference 解析不到：%s' % (len(unresolved), unresolved[:3]))
        bad += 1
    else:
        print('  [通過] 所有 reference 都解析得到目標')

    d = bpmn_handler.extract(bpmn_path)
    ids = [a['id'] for a in d['activities']]
    want = {args.apply_id, args.manager_id}
    if want <= set(ids):
        print('  [通過] 關卡：%s' % '、'.join(ids))
    else:
        print('  [失敗] 關卡缺少 %s（目前 %s）' % (want - set(ids), ids))
        bad += 1

    f = form_handler.extract(form_path)
    print('  表單 ID=%s／名稱=%s／元件 %d 個（空白範本本來就是 0）'
          % (f['formId'], f['formName'], len(f['fields'])))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description='從空白範本複製出一個新的 BPM 專案')
    ap.add_argument('--name', required=True, help='專案／流程／表單的中文名稱')
    ap.add_argument('--form-id', required=True, help='表單英文 ID')
    ap.add_argument('--process-id', required=True, help='流程英文 ID')
    ap.add_argument('--apply-id', default='ApplyUserTask', help='開單關卡 ID')
    ap.add_argument('--manager-id', default='ManagerUserTask', help='主管關卡 ID')
    ap.add_argument('--apply-name', default='開單人', help='開單關卡中文名')
    ap.add_argument('--manager-name', default='直屬主管', help='主管關卡中文名')
    ap.add_argument('--out', default=None, help='輸出目錄（預設 samples/<name>）')
    ap.add_argument('--force', action='store_true', help='輸出目錄已存在時仍然覆蓋')
    args = ap.parse_args(argv)

    for label, value in (('表單 ID', args.form_id), ('流程 ID', args.process_id),
                         ('開單關卡 ID', args.apply_id), ('主管關卡 ID', args.manager_id)):
        _check_id(label, value)

    if args.out is None:
        args.out = os.path.join(ROOT, 'samples', args.name)
    if os.path.exists(args.out) and not args.force:
        raise SystemExit('輸出目錄已存在：%s\n要覆蓋請加 --force' % args.out)
    for sub in ('表單', '流程'):
        d = os.path.join(args.out, sub)
        if not os.path.isdir(d):
            os.makedirs(d)

    oid_base = _oid_base(args.form_id + '|' + args.process_id)
    print('由空白範本複製新專案：%s' % args.name)
    print('  OID 區段 0x%08x…（依 ID 決定，不同專案不會撞號）' % oid_base)

    form_path = build_form(args, oid_base)
    bpmn_path = build_bpmn(args, oid_base)

    meta = {
        'name': args.name,
        'formId': args.form_id,
        'processId': args.process_id,
        'activities': {'apply': args.apply_id, 'manager': args.manager_id},
        'template': '8_BPMAIworker/templates/原始空白專案',
        'oidBase': '0x%08x' % oid_base,
        'oidSuffix': OID_SUFFIX,
    }
    meta_path = os.path.join(args.out, 'project.json')
    io.open(meta_path, 'w', encoding='utf-8', newline='').write(
        json.dumps(meta, ensure_ascii=False, indent=2))

    bad = check(form_path, bpmn_path, args)

    print()
    print('== 下一步 ==')
    print('  1. 加元件到表單（目前是空的）')
    print('  2. 設關卡欄位權限：')
    try:
        shown = os.path.relpath(bpmn_path, ROOT)
    except ValueError:          # 輸出在別的磁碟機時 relpath 會炸
        shown = bpmn_path
    print('     python 8_BPMAIworker/tools/set_permissions.py "%s" --json <權限檔>' % shown)
    print('  3. 檢查：python 8_BPMAIworker/tools/verify.py')
    print()
    print('  空白範本的兩個 UserTask 都還沒有 <formFieldAccessControl>，')
    print('  代表「沿用表單預設權限」。要做出關卡差異一定要跑第 2 步。')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
