# -*- coding: utf-8 -*-
"""設定 .bpmn 各關卡的欄位／按鈕權限。

空白範本的兩個 UserTask 只有 <formFieldAccessDefinition>、沒有
<formFieldAccessControl> —— 那代表「沿用表單預設權限」，關卡之間不會有差異。
要做出「開單人可編輯、主管只能看」這種效果，一定要跑這一步把權限字串寫進去。

權限檔格式（JSON）：

    {
      "formId": "PurchaseForm",
      "activities": {
        "ApplyUserTask":   ["SubjectTextBox", "ContentTextArea", "SubmitButton"],
        "ManagerUserTask": {"RemarkTextArea": "ENABLED", "SubjectTextBox": "INVISIBLE"}
      }
    }

陣列寫法一律 ENABLED；要 INVISIBLE / FULL_CONTROL 就用物件寫法。
**唯讀的作法是不列出這個欄位**，不是寫某個值 —— 鼎新只存三種值。

    python 8_BPMAIworker/tools/set_permissions.py <流程.bpmn> --json <權限檔> [--out <輸出>]

不加 --out 就地覆蓋（會先確認欄位都存在，任何一項不合法就整份不寫）。
"""

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '1_xml_tool'))
sys.path.insert(0, HERE)

from core import xml_utils as X          # noqa: E402
from core import bpmn_handler            # noqa: E402
import bpm_edit                          # noqa: E402


def _form_field_ids(form_path):
    text, _ = X.read_xml(form_path)
    ids = set()
    for s in X.find_blocks(text, lambda n: n.startswith(bpm_edit.FORM_NS)
                           and n.endswith('ElementDefinition')):
        eid = X.child_text(text, s, 'id')
        if eid:
            ids.add(eid)
    return ids


def main(argv=None):
    ap = argparse.ArgumentParser(description='把欄位權限寫進 .bpmn 的各關卡')
    ap.add_argument('bpmn', help='目標 .bpmn')
    ap.add_argument('--json', required=True, help='權限檔')
    ap.add_argument('--out', default=None, help='輸出檔（預設就地覆蓋）')
    ap.add_argument('--form', default=None,
                    help='對照用的 .form；給了就會檢查每個欄位 ID 是否真的存在')
    args = ap.parse_args(argv)

    cfg = json.loads(io.open(args.json, encoding='utf-8').read())
    form_id = cfg.get('formId')
    if not form_id:
        raise SystemExit('權限檔缺少 formId')
    activities = cfg.get('activities') or {}
    if not activities:
        raise SystemExit('權限檔的 activities 是空的，沒有東西可寫')

    text, bom = X.read_xml(args.bpmn)

    # 先全部檢查完再寫，避免寫到一半失敗留下半套檔案
    known = _form_field_ids(args.form) if args.form else None
    problems = []
    for act_id, perms in activities.items():
        if bpm_edit.find_by_child_id(text, bpm_edit.WF_NS + 'ActivityDefinition',
                                     act_id) is None:
            problems.append('流程裡沒有關卡 %s' % act_id)
            continue
        names = perms.keys() if isinstance(perms, dict) else perms
        if known is not None:
            for f in names:
                if f not in known:
                    problems.append('關卡 %s 的欄位 %s 在表單裡不存在' % (act_id, f))
    if problems:
        for p in problems:
            print('  [失敗] ' + p)
        raise SystemExit('權限設定未寫入（欄位 ID 打錯不會報錯，只會靜默失效，'
                         '所以這裡先擋下來）')

    for act_id, perms in activities.items():
        text = bpm_edit.set_field_permissions(text, act_id, form_id, perms)
        n = len(perms)
        print('  %s：%d 項' % (act_id, n))

    out = args.out or args.bpmn
    X.write_xml(out, text, bom)
    print('  輸出 %s' % out)

    d = bpmn_handler.extract(out)
    print()
    print('== 反解確認 ==')
    for a in d['activities']:
        total = len(a['buttons']) + len(a['fieldPermissions'])
        if total:
            print('  %-18s %-10s 按鈕 %d／欄位 %d（表單 %s）'
                  % (a['id'], a['name'], len(a['buttons']),
                     len(a['fieldPermissions']), a.get('formId', '?')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
