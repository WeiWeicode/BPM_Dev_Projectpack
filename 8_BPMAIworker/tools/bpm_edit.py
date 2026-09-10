# -*- coding: utf-8 -*-
"""鼎新 .form / .bpmn 的共用編輯動作。

全部走 `1_xml_tool/core/xml_utils` 的字串區間法，不建 DOM、不重新序列化
（AGENTS.md 7.2：任何重新序列化都會破壞 XStream 參照與空白格式）。

這裡只放「怎麼改」，不放「改成什麼」—— 後者是各 build_*.py 的事。
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '1_xml_tool'))

from core import xml_utils as X          # noqa: E402

WF_NS = 'com.dsc.nana.domain.workflow__definition.'
FORM_NS = 'com.dsc.nana.domain.form.'

PERMISSION_VALUES = ('ENABLED', 'INVISIBLE', 'FULL_CONTROL')


# ---------------------------------------------------------------- 通用定位

def find_by_child_id(text, class_tag, wanted):
    """找出 <class_tag> 底下 <id> 等於 wanted 的那一個區塊。"""
    for s in X.find_blocks(text, lambda n: n == class_tag):
        if X.child_text(text, s, 'id') == wanted:
            return s
    return None


def set_child(text, span, tag, value):
    c = X.child(text, span, tag)
    if c is None:
        raise ValueError('找不到 <%s>' % tag)
    return X.apply_edits(text, [(c.inner_start, c.inner_end, value)])


def cut(text, span):
    """刪掉一個區塊，連同它前面的縮排與換行，不留空行殘骸。"""
    start = span.start
    while start > 0 and text[start - 1] in ' \t':
        start -= 1
    if start > 0 and text[start - 1] == '\n':
        start -= 1
    return text[:start] + text[span.end:]


def drop_all(text, class_tag, ids):
    for wanted in ids:
        s = find_by_child_id(text, class_tag, wanted)
        if s is None:
            raise ValueError('找不到要刪除的 %s：%s' % (class_tag, wanted))
        text = cut(text, s)
    return text


def replace_leaf(text, tag, old, new):
    """把所有 <tag>old</tag> 換成 <tag>new</tag>，回傳 (新文字, 換掉幾處)。

    只比對「葉節點且內容剛好等於 old」，避免誤傷含有相同字串的長文字。
    """
    pat = re.compile(r'<%s>%s</%s>' % (re.escape(tag), re.escape(old), re.escape(tag)))
    return pat.subn('<%s>%s</%s>' % (tag, new, tag), text)


# ---------------------------------------------------------------- OID

def remap_oids(text, prefix_base, suffix):
    """把檔內所有 OID 換成新的一組，避免與線上既有定義撞號。

    prefix_base：前 8 碼的起算整數；suffix：固定的後 24 碼。
    同一個舊 OID 一律對到同一個新 OID，containerOID 的指向才不會斷。
    """
    if len(suffix) != 24:
        raise ValueError('OID 後綴必須是 24 碼，目前 %d 碼' % len(suffix))
    found = []
    for m in re.finditer(r'<(OID|containerOID)>([0-9a-f]{32})</\1>', text):
        if m.group(2) not in found:
            found.append(m.group(2))
    mapping = {}
    for i, old in enumerate(found, 1):
        mapping[old] = '%08x' % (prefix_base + i) + suffix
    if len(set(mapping.values())) != len(mapping):
        raise ValueError('新 OID 產生了重複，請換一個 prefix_base')
    for old, new in mapping.items():
        text = text.replace(old, new)
    return text, len(mapping)


# ---------------------------------------------------------------- 欄位權限

def fac_payload(form_id, permissions):
    """組出 <formFieldAccessControl> 內的二次逃脫字串。

    permissions 可以是 [欄位ID, ...]（一律 ENABLED）或 {欄位ID: 權限值}。
    唯讀的作法是「不列出」，不是寫某個值 —— 鼎新只存三種值。
    """
    if isinstance(permissions, dict):
        items = list(permissions.items())
    else:
        items = [(f, 'ENABLED') for f in permissions]
    for fid, val in items:
        if val not in PERMISSION_VALUES:
            raise ValueError('權限值「%s」不合法（欄位 %s）；只有 %s'
                             % (val, fid, '／'.join(PERMISSION_VALUES)))
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', fid):
            raise ValueError('欄位 ID「%s」不能當 XML 標籤名' % fid)
    inner = ''.join('<%s>%s</%s>' % (f, v, f) for f, v in items)
    return X.xml_escape('<FormFieldAccessControl><%s>%s</%s></FormFieldAccessControl>'
                        % (form_id, inner, form_id))


def set_field_permissions(text, activity_id, form_id, permissions):
    """設定某關卡的欄位權限。

    關卡已有 <formFieldAccessControl> 就換掉內容；只有 <formFieldAccessDefinition>
    （空白範本就是這個狀態）則在它裡面第一順位插一個進去。
    """
    act = find_by_child_id(text, WF_NS + 'ActivityDefinition', activity_id)
    if act is None:
        raise ValueError('找不到關卡 %s' % activity_id)

    payload = fac_payload(form_id, permissions)

    fac = X.find_blocks(text, lambda n: n == 'formFieldAccessControl',
                        act.inner_start, act.inner_end)
    if fac:
        return X.apply_edits(text, [(fac[0].inner_start, fac[0].inner_end, payload)])

    ffad = X.child(text, act, 'formFieldAccessDefinition')
    if ffad is None:
        raise ValueError('關卡 %s 既無 formFieldAccessControl 也無 formFieldAccessDefinition，'
                         '不是可設權限的關卡型別' % activity_id)
    indent = '\n            '
    tag = '%s<formFieldAccessControl>%s</formFieldAccessControl>' % (indent, payload)
    return text[:ffad.inner_start] + tag + text[ffad.inner_start:]


# ---------------------------------------------------------------- .form 專用

def inline_numeric_refs(text):
    """展開 .form 的數字 reference（XStream ID mode）。

    展開後才能安全增刪元件並重新編號 —— 否則 reference="8" 會指到別人身上。
    回傳 (新文字, 展開幾處)。
    """
    spans = X.find_blocks(text, lambda n: True)
    by_id = {}
    for s in spans:
        am = re.search(r'\sid="(\d+)"', s.attrs or '')
        if am:
            by_id[am.group(1)] = s

    edits = []
    for s in spans:
        rm = re.search(r'reference="(\d+)"', s.attrs or '')
        if not rm:
            continue
        target = by_id.get(rm.group(1))
        if target is None:
            raise ValueError('reference="%s" 找不到對應節點' % rm.group(1))
        inner = text[target.inner_start:target.inner_end]
        if 'reference=' in inner:
            raise ValueError('目標含巢狀 reference，需另行處理：%s' % rm.group(1))
        edits.append((s.start, s.end, '<%s>%s</%s>' % (s.name, inner, s.name)))
    return X.apply_edits(text, edits), len(edits)


def renumber_form_ids(text):
    """全檔重編 XStream id（1…N，依文件順序）。前提是已無任何 reference。"""
    if 'reference="' in text:
        raise ValueError('仍有 reference 未展開，重編號會破壞參照')
    counter = [0]

    def repl(_m):
        counter[0] += 1
        return ' id="%d"' % counter[0]

    return re.sub(r'\sid="\d+"', repl, text), counter[0]
