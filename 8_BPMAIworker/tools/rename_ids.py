# -*- coding: utf-8 -*-
"""把 .form / .bpmn 內的表單代號與流程代號換成另一組，讓它匯入時是「新的一支」。

用途：測試區已經有同代號的流程與表單，直接匯入會跳「要不要覆蓋」。
改掉代號就能與既有版本並存，測完再決定要不要真的蓋上去。

    python 8_BPMAIworker/tools/rename_ids.py \\
        --form 表單/MIS_Application_v2.form \\
        --form-id MIS_Application=MIS_Application_v2 \\
        --out out/191匯入_SIC005_v2

代號會出現在好幾個地方，少改一處就會靜默壞掉，所以一律由本工具一次改完：

  .form   <id>                            表單代號本體
          <script> 內的 DataSource("表單ID", "SQL名")

  .bpmn   <id> / <mainProcessDefinitionId>            流程代號
          <formDefinitionId>                          流程變數綁的表單
          <formFieldAccessControl> 內的 &lt;表單ID&gt;   關卡欄位權限（二次逃脫）
          <subjectTemplet> 內的 &lt;#表單ID~~欄位&gt;    主旨範本

改完會一併重配 OID（做法與 new_project.py 相同），避免與線上既有定義撞號。
編輯一律走 1_xml_tool/core 的字串區間法，不重新序列化（AGENTS.md 7.2）。
"""

import argparse
import hashlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '1_xml_tool'))
sys.path.insert(0, HERE)

from core import xml_utils as X          # noqa: E402
from core import form_handler            # noqa: E402
import bpm_edit                          # noqa: E402

ID_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# 本工具自己的 OID 區段，與 new_project.py 的 0x7a1… 錯開，兩邊產出不會撞號
OID_BASE = 0x7b100000
OID_SUFFIX = 'a1de51000851cac97a977dbb'


def _oid_base(seed):
    """依新代號決定 OID 前綴起算值，每組代號配 256 個號。"""
    h = int(hashlib.md5(seed.encode('utf-8')).hexdigest()[:4], 16)
    return OID_BASE + h * 0x100


def _pair(raw, label):
    """解析 OLD=NEW，順便擋掉不合法的代號。

    代號會被當成 XML 標籤名寫進欄位權限字串，不合法的字元會讓權限整段解析不到。
    """
    if '=' not in raw:
        raise SystemExit('%s 要寫成 舊代號=新代號，收到「%s」' % (label, raw))
    old, _, new = raw.partition('=')
    old, new = old.strip(), new.strip()
    for value in (old, new):
        if not ID_RE.match(value):
            raise SystemExit('%s「%s」不合法：只允許英數字與底線、不可數字開頭' % (label, value))
    if old == new:
        raise SystemExit('%s 的新舊代號一樣（%s），沒有東西要改' % (label, old))
    return old, new


def _report(action, count, expected=None):
    mark = '  '
    if expected is not None and count != expected:
        mark = '!!'
    print('  %s %-52s %d 處' % (mark, action, count))
    return expected is None or count == expected


def rename_form(path, form_pairs, out_dir):
    """改 .form 的表單代號，回傳 (輸出路徑, 是否全部符合預期)。"""
    text, bom = X.read_xml(path)
    ok = True
    new_id = None

    for old, new in form_pairs:
        text, n = bpm_edit.replace_leaf(text, 'id', old, new)
        ok &= _report('<id> %s → %s' % (old, new), n, 1)
        if n:
            new_id = new

        # <script> / <mobileScript> 是逃脫過的內容，DataSource 的第一個參數是表單代號
        before = text
        text = text.replace('DataSource(&quot;%s&quot;' % old,
                            'DataSource(&quot;%s&quot;' % new)
        text = text.replace('DataSource("%s"' % old, 'DataSource("%s"' % new)
        hits = 0 if text == before else before.count('DataSource(&quot;%s&quot;' % old) \
            + before.count('DataSource("%s"' % old)
        _report('腳本內 DataSource("%s" → "%s")' % (old, new), hits)
        if not hits:
            print('     （這張表單的腳本沒有 DataSource，屬正常）')

        # 代號若還殘留在別的地方，要讓人知道，不能靜默放過
        leftover = len(re.findall(r'(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])' % re.escape(old), text))
        if leftover:
            print('     [注意] 舊代號 %s 還有 %d 處未改，請人工確認是不是該改'
                  % (old, leftover))

    text, n_oid = bpm_edit.remap_oids(text, _oid_base(new_id or path), OID_SUFFIX)
    _report('重配 OID（含 containerOID）', n_oid)

    out = os.path.join(out_dir, '%s.form' % (new_id or 'renamed'))
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    X.write_xml(out, text, bom)

    # 腳本另存一份，之後要改腳本改這一份再貼回設計器就好（做法同 new_project.py）
    js, _msg = form_handler.extract_script(out)
    js_path = os.path.join(out_dir, '%s.js' % (new_id or 'renamed'))
    io.open(js_path, 'w', encoding='utf-8', newline='').write(js)
    print('  產出 %s（腳本另存 %s）' % (os.path.basename(out), os.path.basename(js_path)))
    return out, ok


def rename_bpmn(path, process_pairs, form_pairs, out_dir):
    """改 .bpmn 的流程代號與它引用的表單代號，回傳 (輸出路徑, 是否全部符合預期)。"""
    text, bom = X.read_xml(path)
    if 'ProcessPackage' not in text:
        raise SystemExit(
            '%s 不是設計器匯出的流程檔。\n'
            '根標籤應為 <com.dsc.nana.domain.workflow__definition.ProcessPackage>；\n'
            '若根標籤是 <Diagram>，那是資料庫 ProcessDefinition.bpmXML，只有畫布座標，\n'
            '不含關卡與權限，無法匯入 —— 要請設計器直接匯出一份。' % path)

    ok = True
    new_id = None
    for old, new in process_pairs:
        # 流程代號的 <id> 至少兩處：ProcessPackage 一個、ProcessDefinition 一個。
        # 兩者不同名的流程（如 GSRNProess）也可能只有一處，故只要求「不是 0」。
        text, n1 = bpm_edit.replace_leaf(text, 'id', old, new)
        _report('<id> %s → %s' % (old, new), n1)
        if not n1:
            ok = False
            print('     [失敗] 找不到 <id>%s</id>，流程代號沒有被改到' % old)
        text, n2 = bpm_edit.replace_leaf(text, 'mainProcessDefinitionId', old, new)
        _report('<mainProcessDefinitionId> %s → %s' % (old, new), n2)
        if n1:
            new_id = new

    for old, new in form_pairs:
        text, n = bpm_edit.replace_leaf(text, 'formDefinitionId', old, new)
        _report('<formDefinitionId> %s → %s' % (old, new), n)

        # 欄位權限是二次逃脫的 XML：&lt;FormFieldAccessControl&gt;&lt;表單ID&gt;…
        opened = text.count('&lt;%s&gt;' % old)
        closed = text.count('&lt;/%s&gt;' % old)
        text = text.replace('&lt;%s&gt;' % old, '&lt;%s&gt;' % new)
        text = text.replace('&lt;/%s&gt;' % old, '&lt;/%s&gt;' % new)
        _report('欄位權限內的 &lt;%s&gt;（起訖各半）' % old, opened + closed)
        if opened != closed:
            ok = False
            print('     [失敗] 起始 %d 個、結束 %d 個對不起來，權限字串可能已損壞'
                  % (opened, closed))

        # 主旨範本：&lt;#表單ID~~欄位ID&gt;
        subject = text.count('&lt;#%s~~' % old)
        text = text.replace('&lt;#%s~~' % old, '&lt;#%s~~' % new)
        _report('主旨範本內的 &lt;#%s~~' % old, subject)

        # 流程變數（relevantDataDefinition）習慣與表單同名，但兩者是各自獨立的識別字。
        # 改了要 16 處引用一起改，不改則流程照樣靠 formDefinitionId 綁到新表單 ——
        # 兩種都合法，故本工具不自行決定，只把殘留處報出來給人判斷。
        leftover = len(re.findall(r'(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])' % re.escape(old), text))
        if leftover:
            print('     [注意] 舊表單代號 %s 還有 %d 處未改（多半是流程變數 '
                  'relevantDataDefinitionId）。' % (old, leftover))
            print('            流程變數名稱與表單代號本來就可以不同，不改也能跑；'
                  '要一致的話請人工改。')

    text, n_oid = bpm_edit.remap_oids(text, _oid_base(new_id or path), OID_SUFFIX)
    _report('重配 OID', n_oid)

    out = os.path.join(out_dir, '%s.bpmn' % (new_id or 'renamed'))
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    X.write_xml(out, text, bom)
    print('  產出 %s' % os.path.basename(out))
    return out, ok


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='把 .form / .bpmn 的表單與流程代號換成另一組，避免匯入時覆蓋既有定義')
    parser.add_argument('--form', help='要改的 .form 路徑')
    parser.add_argument('--bpmn', help='要改的 .bpmn 路徑（必須是設計器匯出的檔）')
    parser.add_argument('--form-id', action='append', default=[],
                        metavar='舊=新', help='表單代號對應，可重複')
    parser.add_argument('--process-id', action='append', default=[],
                        metavar='舊=新', help='流程代號對應，可重複')
    parser.add_argument('--out', required=True, help='輸出目錄')
    args = parser.parse_args(argv)

    if not args.form and not args.bpmn:
        parser.error('至少要給 --form 或 --bpmn 其中一個')

    form_pairs = [_pair(v, '--form-id') for v in args.form_id]
    process_pairs = [_pair(v, '--process-id') for v in args.process_id]
    out_dir = os.path.abspath(args.out)
    ok = True

    if args.form:
        if not form_pairs:
            parser.error('--form 需要搭配 --form-id')
        print('表單 %s' % args.form)
        _, good = rename_form(args.form, form_pairs, out_dir)
        ok &= good

    if args.bpmn:
        if not process_pairs and not form_pairs:
            parser.error('--bpmn 需要搭配 --process-id 或 --form-id')
        print('流程 %s' % args.bpmn)
        _, good = rename_bpmn(args.bpmn, process_pairs, form_pairs, out_dir)
        ok &= good

    print()
    if ok:
        print('改名完成。匯入設計器前請自行確認一次代號有沒有撞到既有定義。')
    else:
        print('改名完成，但有標 !! 的項目次數與預期不符 —— 匯入前先看過那幾處。')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
