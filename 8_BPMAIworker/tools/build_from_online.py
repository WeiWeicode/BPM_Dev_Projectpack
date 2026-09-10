# -*- coding: utf-8 -*-
"""把線上抓下來的表單，改建成以「原始空白專案」為主幹的響應式新專案。

為什麼要重建而不是直接匯入：線上的舊表單是**絕對位置**版面
（`appDesignType=3`、`rwdLayout` 空、每個元件的 cssStyle 帶 `position:absolute`），
直接把 `defSerialize` 匯進設計器，得到的還是絕對位置的舊式表單。
要拿到響應式表單，只能以響應式的骨架重新長一次。

    骨架   templates/原始空白專案/表單/OriginalBlankFormProject.form
           （appDesignType=-1、rwdLayout=[]、0 個元件）
    元件   samples/快速開發測試/表單/原檔案-quickDevTestForm.form
           （27 種型別各一個，響應式、已知可匯入 —— PLAN.md 第 4 節的元件字典）
    內容   線上抓下來的欄位 ID／中文名／型別／選項／座標，與整份 JavaScript

只有「內容」來自線上，**XML 結構一律沿用兩份已知可匯入的檔案**，
不憑空生成標籤（PLAN.md 第 7 節的保守路線）。

    python 8_BPMAIworker/tools/build_from_online.py \\
        --source 8_BPMAIworker/out/190_SIC005_v2 \\
        --form-id MIS_Application_v2 --process-id SIC005_v2 \\
        --name MIS問題反應單 --out 8_BPMAIworker/out/新專案_SIC005_v2
"""

import argparse
import hashlib
import io
import json
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

FORM_NS = 'com.dsc.nana.domain.form.'

SKELETON = os.path.join(HERE, '..', 'templates', '原始空白專案', '表單',
                        'OriginalBlankFormProject.form')
SKELETON_BPMN = os.path.join(HERE, '..', 'templates', '原始空白專案', '流程',
                             'OriginalBlankProcessProject.bpmn')
SKELETON_FORM_ID = 'OriginalBlankFormProject'
SKELETON_PROCESS_ID = 'OriginalBlankProcessProject'
SKELETON_PROCESS_NAME = '原始空白流程專案'

LIBRARY = os.path.join(ROOT, 'samples', '快速開發測試', '表單',
                       '原檔案-quickDevTestForm.form')

# 本工具自己的 OID 區段，與 new_project.py（0x7a1…）、rename_ids.py（0x7b1…）錯開
OID_BASE = 0x7c100000
OID_SUFFIX = 'a1de51000851cac97a977dbb'

ID_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# 線上元件（類別 + controlType）→ 教材檔裡拿哪一個當片段。
# controlType 之後會用來源的值覆寫，所以只要挑到「同一個 XML 類別」就夠。
FRAGMENT_BY_CLASS = {
    'InputElementDefinition': 'TextBox5',
    'SelectElementDefinition': 'Dropdown17',
    'DateElementDefinition': 'Date19',
    'OutputElementDefinition': 'Label3',
    'TriggerElementDefinition': 'Button4',
    'AttachmentElementDefinition': 'Attachment',
    'ImageElementDefinition': 'Image24',
    'SerialNumberElementDefinition': 'SerialNumber9',
}
# 少數 controlType 在教材檔有更貼近的片段，用它可以少改幾個子標籤
FRAGMENT_BY_CONTROL = {
    'INPUT_TEXTAREA_TYPE': 'TextArea6',
    'HIDDEN_TYPE': 'HiddenTextBox7',
    'SELECT_RADIO_TYPE': 'RadioButton15',
    'SELECT_CHECK_TYPE': 'CheckBox16',
    'SELECT_CHECKBOX_TYPE': 'CheckBox16',
}

# 同一列的認定：來源 cssStyle 的 top 差距在這個範圍內視為同一列
ROW_TOLERANCE = 18
# rwdLayout 一列最多切幾格（12 欄格線，4 格 = 每格 3 欄）
MAX_CELLS = 4


# ---------------------------------------------------------------- 來源解析

def _control_type(text, span):
    node = X.child(text, span, 'controlType')
    if node is None:
        return ''
    m = re.search(r'<value>([^<]*)</value>', text, 0)
    m = re.search(r'<value>([^<]*)</value>', text[node.inner_start:node.inner_end])
    return m.group(1) if m else ''


def _coords(text, span):
    """從 cssStyle 取絕對座標，用來還原「原本長什麼樣」的列與欄順序。"""
    css = X.child_text(text, span, 'cssStyle') or ''
    top = re.search(r'top:\s*(-?\d+)', css)
    left = re.search(r'left:\s*(-?\d+)', css)
    return (int(top.group(1)) if top else 0, int(left.group(1)) if left else 0)


def _options(text, span):
    """取下拉／單選／複選的選項，回傳 [(顯示文字, 實際值)]。

    顯示文字與實際值可以不同（`chkfill` 顯示「補單」、值是 `Y`），
    兩個都要搬，只搬顯示文字會讓存進資料庫的值變成中文。
    順序就是執行期 `<欄位ID>_0`、`_1`… 的順序，腳本靠它定位，不能動。
    """
    node = X.child(text, span, 'selectListItems')
    if node is None:
        return []
    seg = text[node.inner_start:node.inner_end]
    options = []
    for item in X.find_blocks(seg, lambda n: n == FORM_NS + 'SelectItem'):
        options.append((X.xml_unescape(X.child_text(seg, item, 'displayValue') or ''),
                        X.xml_unescape(X.child_text(seg, item, 'itemValue') or '')))
    return options


def read_source(form_path):
    """讀線上表單，回傳每個元件的 id／類別／controlType／中文名／選項／座標。

    標籤（OutputElementDefinition）分兩種：配對在輸入欄位旁邊的 `lbl_xxx`，
    以及自己獨立存在的區塊標題。前者是別人的中文名，後者才是一個元件。
    """
    text, _ = X.read_xml(form_path)
    text, _ = bpm_edit.inline_numeric_refs(text)

    blocks = X.find_blocks(
        text, lambda n: n.startswith(FORM_NS) and n.endswith('ElementDefinition'))

    labels = {}
    for span in blocks:
        cls = span.name[len(FORM_NS):]
        if cls != 'OutputElementDefinition':
            continue
        eid = X.child_text(text, span, 'id') or ''
        if eid.startswith('lbl_'):
            labels[eid[4:]] = X.xml_unescape(X.child_text(text, span, 'textValue') or '')

    fields = []
    for span in blocks:
        cls = span.name[len(FORM_NS):]
        eid = X.child_text(text, span, 'id') or ''
        if not eid or eid.startswith('lbl_'):
            continue
        top, left = _coords(text, span)
        fields.append({
            'id': eid,
            'cls': cls,
            'controlType': _control_type(text, span),
            'label': labels.get(eid, ''),
            'caption': X.xml_unescape(X.child_text(text, span, 'caption') or ''),
            # 區塊標題這種沒有配對標籤的元件，中文字放在自己的 textValue
            'ownText': X.xml_unescape(X.child_text(text, span, 'textValue') or ''),
            'options': _options(text, span),
            'top': top,
            'left': left,
            'hasLabel': eid in labels,
        })
    fields.sort(key=lambda f: (f['top'], f['left']))
    return fields


# ---------------------------------------------------------------- 片段複製

def read_library():
    """讀教材檔，回傳 ({元件ID: (類別, 片段原文)}, SelectItem 片段原文)。

    連 SelectItem 也從教材檔取，不自己拼 XML —— 手拼過一次就漏了 `<itemValue>`，
    設計器直接開不起來。凡是要寫進檔案的標籤，一律有真實來源。
    """
    text, _ = X.read_xml(LIBRARY)
    text, _ = bpm_edit.inline_numeric_refs(text)
    out = {}
    for span in X.find_blocks(
            text, lambda n: n.startswith(FORM_NS) and n.endswith('ElementDefinition')):
        eid = X.child_text(text, span, 'id')
        if eid:
            out[eid] = (span.name[len(FORM_NS):], text[span.start:span.end])

    item = None
    for span in X.find_blocks(text, lambda n: n == FORM_NS + 'SelectItem'):
        item = text[span.start:span.end]
        break
    if item is None:
        raise SystemExit('教材檔裡找不到 SelectItem 樣板')
    return out, item


def _set_leaf(fragment, tag, value):
    """換掉片段內第一個 <tag>…</tag> 的內容；找不到就原樣回傳。"""
    pattern = re.compile(r'(<%s>)(.*?)(</%s>)' % (tag, tag), re.S)
    if not pattern.search(fragment):
        # 空標籤形式 <tag/>
        empty = re.compile(r'<%s\s*/>' % tag)
        if empty.search(fragment) and value:
            return empty.sub('<%s>%s</%s>' % (tag, value, tag), fragment, count=1)
        return fragment
    return pattern.sub(lambda m: m.group(1) + value + m.group(3), fragment, count=1)


def _set_control_type(fragment, value):
    """controlType 是 <controlType id="n"><value>X</value></controlType>。"""
    if not value:
        return fragment
    return re.sub(r'(<controlType[^>]*>\s*<value>)([^<]*)(</value>)',
                  lambda m: m.group(1) + value + m.group(3), fragment, count=1)


def _set_options(fragment, options, item_template):
    """把 <selectListItems> 換成來源的選項清單，每一項都由教材檔片段複製而來。"""
    node = re.search(r'<selectListItems[^>]*>.*?</selectListItems>|<selectListItems\s*/>',
                     fragment, re.S)
    if node is None:
        return fragment, False
    if not options:
        return fragment[:node.start()] + '<selectListItems class="list"/>' \
            + fragment[node.end():], True
    body = ''
    for order, (display, value) in enumerate(options, 1):
        item = _set_leaf(item_template, 'displayValue', X.xml_escape(display))
        item = _set_leaf(item, 'itemValue', X.xml_escape(value))
        item = _set_leaf(item, 'itemOrder', str(order))
        item = _set_leaf(item, 'isDefault', 'false')
        body += '\n            ' + item
    replacement = '<selectListItems class="list">%s\n          </selectListItems>' % body
    return fragment[:node.start()] + replacement + fragment[node.end():], True


def build_element(field, library, pair_key, item_template):
    """由教材檔片段複製出一個元件（必要時連同它的標籤）。"""
    # build_from_spec.py 依 IR 型別直接指名片段；線上重建則靠 controlType 與類別推
    source_id = field.get('fragment') \
        or FRAGMENT_BY_CONTROL.get(field['controlType']) \
        or FRAGMENT_BY_CLASS.get(field['cls'])
    if source_id is None or source_id not in library:
        return None, None, '教材檔沒有可用的 %s 片段' % field['cls']

    cls, fragment = library[source_id]

    # 教材檔的片段本來就帶配對標籤時，**一定要跟著產一個**。
    # 只把 <pairId> 清成空字串，設計器會把這個元件當成「只有標籤、沒有輸入元件」
    # （rwd-node-factory.js：`pairId.length === 0` → `{label: …}`），
    # 接著讀 `tElement.input.id` 就炸 `Cannot read properties of undefined (reading 'id')`。
    # 例外是 Label 與分隔線 —— 它們在教材檔裡本來就是空字串，設計器讀的是 label.id。
    source_pair = re.search(r'<pairId>([^<]*)</pairId>', library[source_id][1])
    has_label = field['hasLabel'] or bool(source_pair and source_pair.group(1))

    fragment = _set_leaf(fragment, 'id', field['id'])
    fragment = _set_leaf(fragment, 'name', X.xml_escape(field['id']))
    fragment = _set_control_type(fragment, field['controlType'])
    fragment = _set_leaf(fragment, 'pairId', pair_key if has_label else '')
    if field.get('required'):
        fragment = _set_leaf(fragment, 'isRequired', 'true')
    if field.get('hint'):
        fragment = _set_leaf(fragment, 'hint', X.xml_escape(field['hint']))

    if field['options']:
        fragment, ok = _set_options(fragment, field['options'], item_template)
        if not ok:
            return None, None, '%s 是 %s，片段裡沒有 selectListItems' % (field['id'], cls)

    # 中文字落在哪個標籤，依 form_handler.display_name 的順序決定：
    # 配對標籤的 textValue → 自己的 caption → 自己的 textValue。
    # 輸入類元件的 <textValue> 是「預設值」不是名稱，絕不能拿來放中文名。
    if cls == 'OutputElementDefinition':
        fragment = _set_leaf(fragment, 'textValue',
                             X.xml_escape(field['ownText'] or field['id']))
    elif field['caption']:
        fragment = _set_leaf(fragment, 'caption', X.xml_escape(field['caption']))

    label_fragment = None
    if has_label:
        label_source = field.get('labelFragment') or 'lbl_TextBox5'
        if label_source in library:
            _, label_fragment = library[label_source]
            label_fragment = _set_leaf(label_fragment, 'id', 'lbl_' + field['id'])
            label_fragment = _set_leaf(label_fragment, 'name',
                                       X.xml_escape('lbl_' + field['id']))
            label_fragment = _set_leaf(label_fragment, 'textValue',
                                       X.xml_escape(field['label'] or field['id']))
            label_fragment = _set_leaf(label_fragment, 'pairId', pair_key)
    return fragment, label_fragment, ''


# ---------------------------------------------------------------- 版面

def build_rwd_layout(fields):
    """依來源的絕對座標分列，產生響應式格線版面。

    同一個 top 帶（±18px）的元件視為同一列，列內依 left 由左到右排。
    這樣重建出來的版面與原本的視覺分組一致，而不是把 47 個欄位排成一長條。

    **隱藏欄位一律不進版面。** 教材檔的 HiddenTextBox7、太陽能ECRECN 的 3 個隱藏欄位
    都不在各自的 rwdLayout 裡 —— 隱藏欄位由執行期另外輸出成 hidden input。
    放進格線的話畫面不會畫它，`document.getElementById` 就抓不到，
    腳本會炸「Element is null, id: ...」。
    """
    visible = [f for f in fields if f['controlType'] != 'HIDDEN_TYPE']

    rows, current, last_top = [], [], None
    for field in visible:
        if last_top is None or abs(field['top'] - last_top) <= ROW_TOLERANCE:
            current.append(field)
            last_top = field['top'] if last_top is None else last_top
        else:
            rows.append(current)
            current, last_top = [field], field['top']
    if current:
        rows.append(current)

    layout = []
    for row in rows:
        # 一列超過 MAX_CELLS 就折成多列，格線只有 12 欄，塞太多會擠成一團
        for start in range(0, len(row), MAX_CELLS):
            chunk = row[start:start + MAX_CELLS]
            width = 12 // MAX_CELLS
            layout.append({
                'row': [width] * MAX_CELLS,
                'column': [[12]] * MAX_CELLS,
                'elements': [[{'id': f['id']}] for f in chunk]
                            + [[{}]] * (MAX_CELLS - len(chunk)),
            })

    return layout


# ---------------------------------------------------------------- 組裝

def _oid_base(seed):
    h = int(hashlib.md5(seed.encode('utf-8')).hexdigest()[:4], 16)
    return OID_BASE + h * 0x100


def _replace_block(text, tag, inner):
    """把 <tag …>…</tag>（或 <tag …/>）整段換成新的內容。"""
    pattern = re.compile(r'<%s\b[^>]*?/>|<%s\b[^>]*?>.*?</%s>' % (tag, tag, tag), re.S)
    m = pattern.search(text)
    if m is None:
        raise SystemExit('骨架裡找不到 <%s>' % tag)
    return text[:m.start()] + inner + text[m.end():]


def build_form(fields, form_id, form_name, script, mobile_script, layout=None):
    """把元件、版面、腳本組進空白骨架，回傳 (表單 XML, BOM, 訊息清單)。

    layout 給定時直接採用（build_from_spec.py 由 IR 的 row/col/span 算好了）；
    不給就依來源的絕對座標分列。
    """
    library, item_template = read_library()
    skeleton, bom = X.read_xml(SKELETON)

    parts, messages, built = [], [], []
    for index, field in enumerate(fields, 1):
        pair_key = '%s_pair%d' % (form_id, index)
        element, label, error = build_element(field, library, pair_key, item_template)
        if error:
            messages.append('[跳過] %s：%s' % (field['id'], error))
            continue
        if label:
            parts.append(label)
        parts.append(element)
        built.append(field)

    body = '\n    '.join(parts)
    skeleton = _replace_block(
        skeleton, 'elementDefinitions',
        '<elementDefinitions class="list">\n    %s\n  </elementDefinitions>' % body)

    if layout is None:
        layout = build_rwd_layout(built)
    skeleton = _replace_block(
        skeleton, 'rwdLayout',
        '<rwdLayout>%s</rwdLayout>'
        % X.xml_escape(json.dumps(layout, ensure_ascii=False, separators=(',', ':'))))

    skeleton = _replace_block(skeleton, 'script',
                              '<script>%s</script>' % X.xml_escape(script))
    skeleton = _replace_block(skeleton, 'mobileScript',
                              '<mobileScript>%s</mobileScript>' % X.xml_escape(mobile_script))

    skeleton, n = bpm_edit.replace_leaf(skeleton, 'id', SKELETON_FORM_ID, form_id)
    if n != 1:
        raise SystemExit('骨架的表單 <id> 應該只有 1 處，實際 %d 處' % n)
    skeleton, _ = bpm_edit.replace_leaf(skeleton, 'name', SKELETON_FORM_ID,
                                        X.xml_escape(form_name))

    skeleton, _ = bpm_edit.remap_oids(skeleton, _oid_base(form_id), OID_SUFFIX)
    skeleton, total = bpm_edit.renumber_form_ids(skeleton)
    messages.append('XStream id 重編 1…%d' % total)
    return skeleton, bom, messages, built


def build_bpmn(process_id, process_name, form_id):
    """由空白骨架產生流程檔，只換代號與名稱（做法完全比照 new_project.py）。"""
    text, bom = X.read_xml(SKELETON_BPMN)
    text, n1 = bpm_edit.replace_leaf(text, 'id', SKELETON_PROCESS_ID, process_id)
    text, n2 = bpm_edit.replace_leaf(text, 'mainProcessDefinitionId',
                                     SKELETON_PROCESS_ID, process_id)
    text, n3 = bpm_edit.replace_leaf(text, 'name', SKELETON_PROCESS_NAME,
                                     X.xml_escape(process_name))
    if (n1, n2, n3) != (2, 1, 2):
        raise SystemExit('流程識別字的處數與預期不符（id=%d, main=%d, name=%d）'
                         % (n1, n2, n3))

    # 表單繫結有四處：關卡是靠 relevantDataDefinitionId 找到表單的，少改一處就綁不到
    total = 0
    for tag in ('formDefinitionId', 'relevantDataDefinitionId', 'id', 'name'):
        text, n = bpm_edit.replace_leaf(
            text, tag, SKELETON_FORM_ID,
            X.xml_escape(process_name) if tag == 'name' else form_id)
        total += n
    if total != 4:
        raise SystemExit('表單繫結參照應為 4 處，實際 %d 處' % total)

    text, _ = bpm_edit.remap_oids(text, _oid_base(process_id), OID_SUFFIX)
    return text, bom, (n1, n2, n3, total)


# ---------------------------------------------------------------- 驗證

def check_layout_ids(out_form):
    """版面裡的每個 ID 都必須有對應的元件定義。

    這是設計器 `TypeError: Cannot read properties of null (reading 'type')` 的成因
    —— 它照著 rwdLayout 逐格找元件，找不到就拿 null 讀 `.type`。

    反過來不成立：元件定義多於版面是正常的。教材檔 47 個元件只有 26 個進版面，
    太陽能ECRECN 140 個只有 39 個 —— 配對標籤與隱藏欄位本來就不進版面。
    """
    text, _ = X.read_xml(out_form)
    layout = json.loads(X.xml_unescape(
        re.search(r'<rwdLayout>(.*?)</rwdLayout>', text, re.S).group(1)))
    in_layout = set()
    for row in layout:
        if row.get('id'):
            in_layout.add(row['id'])
        for cell in row.get('elements', []):
            for entry in cell:
                if entry.get('id'):
                    in_layout.add(entry['id'])
    defined = set()
    for span in X.find_blocks(
            text, lambda n: n.startswith(FORM_NS) and n.endswith('ElementDefinition')):
        eid = X.child_text(text, span, 'id')
        if eid:
            defined.add(eid)
    dangling = sorted(in_layout - defined)
    print('  版面 %d 個 ID、元件 %d 個' % (len(in_layout), len(defined)))
    if dangling:
        print('  [失敗] 版面指到不存在的元件（設計器會開不起來）：%s' % '、'.join(dangling))
    return not dangling


def check_select_items(out_form):
    """每個選項都要有 displayValue 與 itemValue。

    手拼 SelectItem 時漏過 `<itemValue>`，設計器直接開不起來 —— 補這道檢查。
    """
    text, _ = X.read_xml(out_form)
    bad = []
    for span in X.find_blocks(text, lambda n: n == FORM_NS + 'SelectItem'):
        seg = text[span.start:span.end]
        if '<itemValue>' not in seg or '<displayValue>' not in seg:
            bad.append(span.start)
    total = len(X.find_blocks(text, lambda n: n == FORM_NS + 'SelectItem'))
    print('  選項 %d 個，缺 displayValue／itemValue 的 %d 個' % (total, len(bad)))
    return not bad


# 設計師 rwd-node-factory.js 的 convert2JavaScriptType：類別（＋controlType）→ 內部型別。
# 這張表是照著那支檔案抄的，改鼎新版本時要重新對一次。
_JS_TYPE_BY_CLASS = {
    'AttachmentElementDefinition': 'Attachment',
    'BarcodeElementDefinition': 'Barcode',
    'DateElementDefinition': 'DateElement',
    'DialogInputElementDefinition': 'DialogInput',
    'DoubleTextElementDefinition': 'DoubleTextBox',
    'TripleTextElementDefinition': 'TripleTextBox',
    'DialogInputLabelElementDefinition': 'DialogInputLabel',
    'DialogInputMultiElementDefinition': 'DialogInputMulti',
    'HorizontalLineElementDefinition': 'HorizontalLine',
    'ImageElementDefinition': 'Image',
    'LinkElementDefinition': 'Link',
    'ListElementDefinition': 'Grid',
    'OutputElementDefinition': 'Label',
    'SerialNumberElementDefinition': 'SerialNumber',
    'TimeElementDefinition': 'Time',
    'TriggerElementDefinition': 'Button',
    'TitleElementDefinition': 'Title',
    'SubTabElementDefinition': 'SubTab',
    'QRCodeElementDefinition': 'QRCode',
    'HandWritingElementDefinition': 'HandWriting',
}
_JS_TYPE_BY_CONTROL = {
    'INPUT_TYPE': 'TextBox',
    'INPUT_SECRET_TYPE': 'Password',
    'INPUT_TEXTAREA_TYPE': 'TextArea',
    'HIDDEN_TYPE': 'HiddenTextBox',
    'SELECT_COMBO_TYPE': 'Dropdown',
    'SELECT_LIST_TYPE': 'ListBox',
    'SELECT_RADIO_TYPE': 'RadioButton',
    'SELECT_CHECK_TYPE': 'CheckBox',
}


def _js_type(cls, control_type):
    if cls in ('InputElementDefinition', 'SelectElementDefinition'):
        # JS 的 switch 沒有 default，控制項種類對不上會往下掉到 Link／SerialNumber，
        # 這裡回 None 當成「設計師認不得」，由呼叫端報出來
        return _JS_TYPE_BY_CONTROL.get(control_type)
    return _JS_TYPE_BY_CLASS.get(cls)


def check_designer_load(out_form):
    """照著設計師 rwd-node-factory.js 的 rebuild() 走一遍，找出開檔會炸的元件。

    L1 的反解對比只能保證「我們讀得回來」，讀得回來不等於設計師開得起來。
    這個檢查把設計師真正的載入邏輯搬過來，堵住兩個已經踩過的坑：

    1. `<pairId>` 是空字串時，設計師一律歸類成「只有標籤、沒有輸入元件」
       （`pairId.length === 0` → `{label: …}`）。隱藏欄位接著讀 `tElement.input.id`
       → `Cannot read properties of undefined (reading 'id')`；
       其他型別則整個不進 tRegularElements，版面找不到它再炸一次。
       Label 與 HorizontalLine 例外：設計師對這兩種讀的是 `label.id`。
    2. 版面（rwdLayout）點到的元件必須在 tRegularElements 裡，否則
       `showMsg("Element is null…")` 之後 `tElement.type` 又是一個例外。
    """
    text, _ = X.read_xml(out_form)
    text, _ = bpm_edit.inline_numeric_refs(text)

    problems = []
    pair_objs = {}
    non_pair = []
    for span in X.find_blocks(
            text, lambda n: n.startswith(FORM_NS) and n.endswith('ElementDefinition')):
        cls = span.name[len(FORM_NS):]
        eid = X.child_text(text, span, 'id')
        control = _control_type(text, span)
        js_type = _js_type(cls, control)
        if js_type is None:
            problems.append('%s：設計師認不得 %s／controlType=%s'
                            % (eid, cls, control or '(無)'))
            continue
        node = X.child(text, span, 'pairId')
        pair_id = None if node is None else text[node.inner_start:node.inner_end]
        entry = {'id': eid, 'cls': cls, 'type': js_type}
        if pair_id is None:
            non_pair.append(dict(entry, slot='label' if js_type == 'Label' else 'input'))
        elif pair_id == '':
            # 這一行就是設計師的判定：空字串一律當成「只有標籤」
            non_pair.append(dict(entry, slot='label'))
        else:
            group = pair_objs.setdefault(pair_id, {})
            group['label' if js_type == 'Label' else 'input'] = entry
            if js_type != 'Label':
                group['type'] = js_type

    # 舊表單常見的 lbl_xxx 與 xxx 隱式配對，設計師會自己併起來
    by_id = dict([(e['id'], e) for e in non_pair])
    merged = set()
    for entry in non_pair:
        if entry['slot'] == 'input' and 'lbl_' + entry['id'] in by_id:
            merged.add(entry['id'])
            merged.add('lbl_' + entry['id'])
            pair_objs['_implicit_' + entry['id']] = {
                'input': entry, 'label': by_id['lbl_' + entry['id']], 'type': entry['type']}
    elements = [e for e in non_pair if e['id'] not in merged] + list(pair_objs.values())

    known = {}
    for element in elements:
        js_type = element.get('type')
        label = element.get('label')
        given = element.get('input')
        if element.get('slot') == 'label':
            label, given = element, None
        elif element.get('slot') == 'input':
            given = element

        if js_type in ('Label', 'HorizontalLine'):
            if label is None:
                problems.append('%s：設計師會讀 tElement.label.id，但這一組沒有標籤'
                                % (given or {}).get('id', '?'))
            else:
                known[label['id']] = js_type
        elif js_type == 'HiddenTextBox':
            if given is None:
                problems.append('%s：pairId 是空字串，設計師把隱藏欄位當成只有標籤，'
                                "接著讀 tElement.input.id 會丟 "
                                "Cannot read properties of undefined (reading 'id')"
                                % label['id'])
            else:
                known[given['id']] = js_type
        elif given is not None:
            known[given['id']] = js_type
        elif label is not None and label['cls'] == 'OutputElementDefinition':
            known[label['id']] = 'Label'
        else:
            orphan = label or given or {}
            problems.append('%s（%s）：pairId 是空字串又不是標籤，設計師不會建這個元件，'
                            '版面點到它就會炸'
                            % (orphan.get('id', '?'), orphan.get('cls', '?')))

    layout = json.loads(X.xml_unescape(
        re.search(r'<rwdLayout>(.*?)</rwdLayout>', text, re.S).group(1)) or '[]')
    for row in layout:
        wanted = []
        if row.get('rowType'):
            wanted.append(row['id'])
        for cell in row.get('elements', []):
            for item in cell:
                if item.get('id'):
                    wanted.append(item['id'])
        for eid in wanted:
            if eid not in known:
                problems.append('版面點到 %s，但設計師的元件表裡沒有它' % eid)

    print('  設計師載入模擬：可建出 %d 個元件，有問題的 %d 項' % (len(known), len(problems)))
    for item in problems:
        print('  [失敗] %s' % item)
    return not problems


def check_pair_ids(out_form):
    """<pairId> 不可以是空字串（Label 與分隔線除外），非空的一定要剛好兩個元件共用。

    這是設計器 `Cannot read properties of undefined (reading 'id')` 的成因：
    rwd-node-factory.js 依 pairId 把元件分成「配對」與「非配對」兩組，
    `pairId.length === 0` 一律歸類成「只有標籤」，之後對隱藏欄位讀 `tElement.input.id`
    就會拿 undefined 去讀屬性；其他型別則整個從 tRegularElements 消失，
    版面找不到它，又變成另一個 null 例外。

    Label（OutputElementDefinition）與 HorizontalLine 的 pairId 在教材檔裡本來就是空字串，
    設計器對這兩種讀的是 `tElement.label.id`，所以是安全的。
    """
    text, _ = X.read_xml(out_form)
    safe_empty = ('OutputElementDefinition', 'HorizontalLineElementDefinition')
    pairs = {}
    bad = []
    for span in X.find_blocks(
            text, lambda n: n.startswith(FORM_NS) and n.endswith('ElementDefinition')):
        cls = span.name[len(FORM_NS):]
        eid = X.child_text(text, span, 'id')
        node = X.child(text, span, 'pairId')
        if node is None:
            continue
        value = text[node.inner_start:node.inner_end]
        if not value:
            if cls not in safe_empty:
                bad.append('%s（%s）的 pairId 是空字串' % (eid, cls))
            continue
        pairs.setdefault(value, []).append(eid)
    for value, members in sorted(pairs.items()):
        if len(members) != 2:
            bad.append('pairId「%s」被 %d 個元件用：%s'
                       % (value, len(members), '、'.join(members)))
    print('  配對 %d 組，pairId 有問題的 %d 項' % (len(pairs), len(bad)))
    for item in bad:
        print('  [失敗] %s（設計器開檔會丟 Cannot read properties of undefined）' % item)
    return not bad


def verify(out_form, source_fields, built):
    """反解產出的 .form，逐項與來源比對（PLAN.md 的 L1）。"""
    result = form_handler.extract(out_form)
    produced = {f['id']: f for f in result.get('fields', [])}
    expected = {f['id'] for f in built}

    missing = sorted(expected - set(produced))
    extra = sorted(set(produced) - expected)
    print('  反解得到 %d 個欄位，預期 %d 個' % (len(produced), len(expected)))
    if missing:
        print('  [失敗] 產出裡少了：%s' % '、'.join(missing))
    if extra:
        print('  [注意] 產出裡多了：%s' % '、'.join(extra))

    skipped = [f['id'] for f in source_fields if f['id'] not in expected]
    if skipped:
        print('  [失敗] 來源有、但沒建出來的欄位：%s' % '、'.join(skipped))
    return not missing and not skipped


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='把線上抓下來的表單改建成以原始空白專案為主幹的響應式新專案')
    parser.add_argument('--source', required=True,
                        help='fetch_online.py 的產出目錄，例如 out/190_SIC005_v2')
    parser.add_argument('--form-id', required=True, help='新表單代號')
    parser.add_argument('--process-id', required=True, help='新流程代號')
    parser.add_argument('--name', required=True, help='中文名稱（表單與流程共用）')
    parser.add_argument('--script', default='',
                        help='要注入的表單 JavaScript 路徑，預設用來源抓到的原始腳本')
    parser.add_argument('--out', required=True, help='輸出目錄')
    args = parser.parse_args(argv)

    for label, value in (('--form-id', args.form_id), ('--process-id', args.process_id)):
        if not ID_RE.match(value):
            raise SystemExit('%s「%s」不合法：只允許英數字與底線、不可數字開頭'
                             % (label, value))

    form_dir = os.path.join(args.source, '表單')
    script_dir = os.path.join(args.source, '腳本')
    candidates = [f for f in os.listdir(form_dir) if f.endswith('.form')]
    if len(candidates) != 1:
        raise SystemExit('%s 裡有 %d 個 .form，請確認來源目錄' % (form_dir, len(candidates)))
    source_form = os.path.join(form_dir, candidates[0])
    stem = candidates[0][:-len('.form')]

    script_path = args.script or os.path.join(script_dir, stem + '.js')
    mobile_path = os.path.join(script_dir, stem + '.mobile.js')
    script = io.open(script_path, encoding='utf-8').read() if os.path.isfile(script_path) else ''
    mobile = io.open(mobile_path, encoding='utf-8').read() if os.path.isfile(mobile_path) else ''

    print('來源表單 %s' % source_form)
    fields = read_source(source_form)
    print('  讀到 %d 個元件（不含配對標籤）' % len(fields))
    print('腳本 %s（%d 字）、手機版 %d 字' % (os.path.basename(script_path), len(script), len(mobile)))

    print('組裝表單（骨架＝原始空白專案，元件＝快速開發測試教材檔）')
    text, bom, messages, built = build_form(fields, args.form_id, args.name, script, mobile)
    for message in messages:
        print('  ' + message)

    out_dir = os.path.abspath(args.out)
    form_out = os.path.join(out_dir, '表單', args.form_id + '.form')
    for folder in (os.path.join(out_dir, '表單'), os.path.join(out_dir, '流程')):
        if not os.path.isdir(folder):
            os.makedirs(folder)
    X.write_xml(form_out, text, bom)
    io.open(os.path.join(out_dir, '表單', args.form_id + '.js'),
            'w', encoding='utf-8', newline='').write(script)
    print('  產出 %s' % os.path.relpath(form_out, out_dir))

    print('組裝流程（骨架＝原始空白專案）')
    bpmn_text, bpmn_bom, counts = build_bpmn(args.process_id, args.name, args.form_id)
    bpmn_out = os.path.join(out_dir, '流程', args.process_id + '.bpmn')
    X.write_xml(bpmn_out, bpmn_text, bpmn_bom)
    print('  代號 %d 處、mainProcessDefinitionId %d 處、名稱 %d 處、表單繫結 %d 處'
          % counts)
    print('  產出 %s' % os.path.relpath(bpmn_out, out_dir))

    print('驗證（反解對比，PLAN.md 的 L1）')
    good = verify(form_out, fields, built)
    good = check_layout_ids(form_out) and good
    good = check_select_items(form_out) and good
    good = check_pair_ids(form_out) and good
    good = check_designer_load(form_out) and good

    print()
    if good:
        print('組裝完成。這是 L1 通過，匯入設計器（L2）與實跑（L3）仍須人工。')
    else:
        print('組裝完成，但反解對比有落差 —— 匯入前先處理上面標 [失敗] 的項目。')
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
