# -*- coding: utf-8 -*-
"""表單 (.form) 萃取與回寫模組。

萃取：以「配對 Label 的 textValue」作為中文名稱，輸出欄位清單。
      完全不輸出 <script> / <mobileScript> / <rwdLayout> / cssStyle / 座標 / 色彩。
回寫：以 originalId 為主鍵定位元件，更新：
      1. 元件與其 Label 的 <id> 與 <name>
      2. <rwdLayout> 內的元件 ID 版面參照
      3. <script> / <mobileScript> 內的表格事件函式 (${GridId}_add_onclick) 與物件變數 (${GridId}Obj)
"""

import re

from . import xml_utils as X

ELEMENT_SUFFIX = 'ElementDefinition'
FORM_NS = 'com.dsc.nana.domain.form.'

# <controlType><value>?</value></controlType> -> 對外顯示的型別
CONTROL_TYPE_MAP = {
    'INPUT_TYPE': 'TEXTBOX',
    'INPUT_TEXTAREA_TYPE': 'TEXTAREA',
    'INPUT_PASSWORD_TYPE': 'PASSWORD',
    'HIDDEN_TYPE': 'HIDDEN',
    'SELECT_RADIO_TYPE': 'RADIO',
    'SELECT_CHECKBOX_TYPE': 'CHECKBOX',
    'SELECT_LIST_TYPE': 'DROPDOWN',
    'DIALOG_DATE': 'DATE',
    'DIALOG_DATETIME': 'DATETIME',
    'DIALOG_TIME': 'TIME',
}

CLASS_TYPE_MAP = {
    'TriggerElementDefinition': 'BUTTON',
    'SerialNumberElementDefinition': 'SERIAL_NUMBER',
    'HorizontalLineElementDefinition': 'HORIZONTAL_LINE',
    'OutputElementDefinition': 'LABEL',
    'DateElementDefinition': 'DATE',
    'InputElementDefinition': 'TEXTBOX',
    'SelectElementDefinition': 'SELECT',
    'GridElementDefinition': 'GRID',
    'AttachmentElementDefinition': 'ATTACHMENT',
}

ID_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_VALUE_RE = re.compile(r'<value>([^<]*)</value>')


class FormElement(object):
    """一個表單元件（或 Label）在原始 XML 中的位置與內容。"""

    def __init__(self, text, span):
        self.span = span
        self.cls = span.name[len(FORM_NS):] if span.name.startswith(FORM_NS) else span.name
        kids = X.direct_children(text, span)
        self.kids = kids
        self.id = X.child_text(text, span, 'id', kids)
        self.name = X.child_text(text, span, 'name', kids)
        self.pair_id = X.child_text(text, span, 'pairId', kids)
        self.text_value = X.xml_unescape(X.child_text(text, span, 'textValue', kids))
        self.caption = X.xml_unescape(X.child_text(text, span, 'caption', kids))
        self.control_type = ''
        ct = X.child(text, span, 'controlType', kids)
        if ct is not None:
            m = _VALUE_RE.search(text, ct.inner_start, ct.inner_end)
            if m:
                self.control_type = m.group(1)
        self.label = None
        self.is_label = (self.cls == 'OutputElementDefinition')

    @property
    def type_name(self):
        if self.cls == 'TriggerElementDefinition':
            return 'BUTTON'
        if self.control_type in CONTROL_TYPE_MAP:
            return CONTROL_TYPE_MAP[self.control_type]
        if self.cls in CLASS_TYPE_MAP:
            return CLASS_TYPE_MAP[self.cls]
        return self.cls.replace(ELEMENT_SUFFIX, '').upper()

    @property
    def display_name(self):
        """對外的中文名稱。"""
        if self.label is not None and self.label.text_value.strip():
            return self.label.text_value
        if self.caption.strip():
            return self.caption
        if self.text_value.strip():
            return self.text_value
        return self.id


def _parse(text):
    """回傳 (全部元件, 配對後依版面順序排列的元件)。"""
    spans = X.find_blocks(
        text,
        lambda n: n.startswith(FORM_NS) and n.endswith(ELEMENT_SUFFIX))
    elements = [FormElement(text, s) for s in spans]

    labels = [e for e in elements if e.is_label]
    controls = [e for e in elements if not e.is_label]

    by_id = {}
    for lb in labels:
        by_id.setdefault(lb.id, lb)
    by_pair = {}
    for lb in labels:
        if lb.pair_id:
            by_pair.setdefault(lb.pair_id, []).append(lb)

    used = set()
    for c in controls:
        lb = by_id.get('lbl_' + c.id) if c.id else None
        if lb is None and c.pair_id:
            for cand in by_pair.get(c.pair_id, []):
                if id(cand) not in used:
                    lb = cand
                    break
        if lb is not None:
            c.label = lb
            used.add(id(lb))

    # 沒被配對走的 Label = 純標題文字，自成一筆
    standalone = [lb for lb in labels if id(lb) not in used]
    ordered = sorted(controls + standalone, key=lambda e: e.span.start)
    return elements, ordered


def _form_meta(text):
    root = X.find_blocks(text, lambda n: n == FORM_NS + 'FormDefinition')
    if not root:
        return '', ''
    kids = X.direct_children(text, root[0])
    return (X.child_text(text, root[0], 'id', kids),
            X.xml_unescape(X.child_text(text, root[0], 'name', kids)))


def extract_text(text, source_name=''):
    """已讀入的 .form 內容 -> dict。供直接從資料庫取得 XML 時使用，免落地暫存檔。"""
    form_id, form_name = _form_meta(text)
    _all, ordered = _parse(text)

    fields = []
    for e in ordered:
        fields.append({
            'name': e.display_name,
            'originalId': e.id,
            'id': e.id,
            'type': e.type_name,
        })

    return {
        'fileType': 'FORM',
        'formId': form_id,
        'formName': form_name,
        'sourceFile': source_name,
        'fields': fields,
    }


def extract(path):
    """.form -> dict（可直接 json.dump）。"""
    text, _bom = X.read_xml(path)
    return extract_text(text, path.replace('\\', '/').split('/')[-1])


def write_back(xml_path, config, out_path):
    """依 config（extract 的結構，id 已被人工修改）回寫成 out_path。

    回傳 (更新筆數, 提醒訊息清單)。驗證失敗一律丟 ValueError，不產生檔案。
    """
    text, bom = X.read_xml(xml_path)
    all_elements, _ordered = _parse(text)

    by_original = {}
    for e in all_elements:
        if e.id:
            by_original.setdefault(e.id, e)

    fields = config.get('fields') or []
    messages = []
    renames = []
    seen_new = {}

    for f in fields:
        old = (f.get('originalId') or '').strip()
        new = (f.get('id') or '').strip()
        title = f.get('name') or old
        if not old:
            raise ValueError('JSON 中有項目缺少 originalId，無法定位元件（name=%s）' % title)
        if old not in by_original:
            raise ValueError('原始檔中找不到 originalId：%s（名稱：%s）' % (old, title))
        if not new:
            raise ValueError('欄位「%s」的 id 不可為空' % title)
        if old == new:
            continue
        if not ID_PATTERN.match(new):
            raise ValueError('新 ID「%s」格式不合法：僅允許英數字與底線，且不可數字開頭' % new)
        if new in seen_new:
            raise ValueError('JSON 內新 ID 重複：%s' % new)
        seen_new[new] = old
        renames.append((old, new, title))

    rename_map = dict((o, n) for o, n, _ in renames)

    # 檢查改名後全表單 ID 仍唯一（含 lbl_ 連動）
    final_ids = {}
    for e in all_elements:
        if not e.id:
            continue
        if e.id in rename_map:
            target = rename_map[e.id]
        elif e.is_label and e.id.startswith('lbl_') and e.id[4:] in rename_map:
            target = 'lbl_' + rename_map[e.id[4:]]
        else:
            target = e.id
        if target in final_ids:
            raise ValueError('ID 衝突：元件「%s」與「%s」改名後都會變成「%s」'
                             % (final_ids[target], e.id, target))
        final_ids[target] = e.id

    edits = []
    changed = 0
    for old, new, title in renames:
        e = by_original[old]
        _queue_id_name_edits(text, e, old, new, edits, messages)
        lb = e.label
        if lb is not None:
            if lb.id == 'lbl_' + old:
                _queue_id_name_edits(text, lb, lb.id, 'lbl_' + new, edits, messages)
            else:
                messages.append('! 「%s」的標籤 ID 為「%s」，不符 lbl_ 命名慣例，已保留不動'
                                % (title, lb.id))
        changed += 1

    # 3. 同步更新 <rwdLayout> 內的元件 ID 參照（避免 BPM 前端解析版面時因找不到元件拋出 TypeError）
    rwd_spans = X.find_blocks(text, lambda n: n == 'rwdLayout')
    rwd_hits = 0
    for rwd_span in rwd_spans:
        raw_rwd = text[rwd_span.inner_start:rwd_span.inner_end]
        new_rwd = raw_rwd
        for old, new, _ in renames:
            pattern = re.compile(
                r'(&quot;id&quot;|"id")\s*:\s*(&quot;|")' + re.escape(old) + r'(&quot;|")'
            )
            def _repl(m, n=new):
                return m.group(1) + ':' + m.group(2) + n + m.group(3)
            new_rwd, count = pattern.subn(_repl, new_rwd)
            rwd_hits += count
        if new_rwd != raw_rwd:
            edits.append((rwd_span.inner_start, rwd_span.inner_end, new_rwd))

    if rwd_hits:
        messages.append('  RWD 版面配置 (<rwdLayout>) 同步更新了 %d 處元件 ID' % rwd_hits)

    # 4. 同步更新 <script> / <mobileScript> 中的 Grid 事件函式與物件變數
    script_spans = X.find_blocks(text, lambda n: n in ('script', 'mobileScript'))
    script_hits = 0
    for s_span in script_spans:
        raw_script = text[s_span.inner_start:s_span.inner_end]
        new_script = raw_script
        for old, new, _ in renames:
            p1 = re.compile(r'\b' + re.escape(old) + r'_(add|edit|delete)_onclick\b')
            new_script, c1 = p1.subn(new + r'_\1_onclick', new_script)
            p2 = re.compile(r'\b' + re.escape(old) + r'Obj\b')
            new_script, c2 = p2.subn(new + 'Obj', new_script)
            script_hits += (c1 + c2)
        if new_script != raw_script:
            edits.append((s_span.inner_start, s_span.inner_end, new_script))

    if script_hits:
        messages.append('  表單腳本 (<script>) 同步更新了 %d 處表格事件與物件參照' % script_hits)

    if not edits:
        return 0, messages

    X.write_xml(out_path, X.apply_edits(text, edits), bom)
    return changed, messages


def _queue_id_name_edits(text, element, old_id, new_id, edits, messages):
    id_span = X.child(text, element.span, 'id', element.kids)
    if id_span is None:
        raise ValueError('元件缺少 <id> 節點，無法回寫：%s' % old_id)
    edits.append((id_span.inner_start, id_span.inner_end, new_id))

    name_span = X.child(text, element.span, 'name', element.kids)
    if name_span is None:
        return
    current = text[name_span.inner_start:name_span.inner_end]
    if current == old_id:
        edits.append((name_span.inner_start, name_span.inner_end, new_id))
    else:
        messages.append('! 元件「%s」的 <name> 為「%s」（不等於舊 ID），已保留不動'
                        % (old_id, current))

