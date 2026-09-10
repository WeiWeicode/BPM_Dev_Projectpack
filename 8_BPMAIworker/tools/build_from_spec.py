# -*- coding: utf-8 -*-
"""由 IR（AI 寫的意圖規格）組出可匯入的 .form / .js / .bpmn。

`build_from_online.py` 走的是「線上已經有一支流程可以照抄」那條路；
這支走的是另一條 —— 手上只有**一張表單截圖或一份欄位清單**，
內容由 AI 依 [docs/AI產生規格_IR.md](../docs/AI產生規格_IR.md) 寫成 IR，
結構則一律沿用既有的、已知可匯入的檔案：

    表單與流程外殼   templates/原始空白專案/
    表單元件字典     samples/快速開發測試/表單/原檔案-quickDevTestForm.form（27 種型別各一個）
    通知關卡片段     samples/快速開發測試/流程/已完成匯入_測試快速開發-欄位權限.bpmn

AI 只決定「有哪些欄位、叫什麼、排第幾列、哪一關能改」；
XStream 連號 id、32 碼 OID、二次逃脫的權限字串一律由本程式配
（README.md 第 2 節：這三件事 LLM 逐字生成必然出錯，而且錯了不報錯）。

    python 8_BPMAIworker/tools/build_from_spec.py \
        --form-ir out/人員需求申請單/form_ir.json \
        --process-ir out/人員需求申請單/process_ir.json \
        --out out/人員需求申請單

只給 --form-ir 就只產表單；流程沿用空白範本要另外跑 new_project.py。
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
from core import bpmn_handler            # noqa: E402
from core import form_handler            # noqa: E402
import bpm_edit                          # noqa: E402
import xstream_ref                       # noqa: E402
import build_from_online as online       # noqa: E402

WF = bpm_edit.WF_NS

BLANK_BPMN = online.SKELETON_BPMN
BLANK_FORM_ID = online.SKELETON_FORM_ID
BLANK_PROCESS_ID = online.SKELETON_PROCESS_ID
BLANK_PROCESS_NAME = online.SKELETON_PROCESS_NAME
LIBRARY_BPMN = os.path.join(ROOT, 'samples', '快速開發測試', '流程',
                            '已完成匯入_測試快速開發-欄位權限.bpmn')
# 教材檔的通知關卡綁的是它自己的表單，搬過來要先改回空白範本的代號，
# 後面的表單繫結替換才會一次改乾淨
LIBRARY_FORM_ID = 'quickDevTestFormImport'

# 本工具自己的 OID 區段（new_project 0x7a1…／rename_ids 0x7b1…／build_from_online 0x7c1…）
OID_BASE = 0x7d100000
OID_SUFFIX = online.OID_SUFFIX
# 組裝過程用的暫時 OID：後綴刻意與任何既有檔案都不同，確保複製出來的關卡不會與來源撞號
WORK_BASE = 0x9e000000
WORK_SUFFIX = 'b2ef71000851cac97a977dbb'

ID_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# IR 型別 → (教材檔片段 ID, controlType, 中文名放哪裡)
#   pair         產生配對標籤 lbl_<欄位ID>，中文名寫在標籤的 textValue（絕大多數欄位）
#   pair_caption 兩個都要：配對標籤放中文名，自己的 <caption> 放連結文字
#   caption      中文名寫進自己的 <caption>（按鈕、附件）
#   own          中文名寫進自己的 <textValue>（純文字標籤）
#   none         不帶中文名（分隔線、圖片、QRCode）
# **教材檔片段本來就有配對標籤的型別，這裡一定要標 pair**：只留一個空的 <pairId>，
# 設計器會把它當成「只有標籤沒有輸入元件」，開檔就丟
# Cannot read properties of undefined (reading 'id')。隱藏欄與超連結都踩過這個坑。
# controlType 取自教材檔實測值，不是猜的（見 docs/從需求生成手冊.md 第 5 節）
ELEMENT_TYPES = {
    'TEXTBOX':          ('TextBox5', 'INPUT_TYPE', 'pair'),
    'TEXTAREA':         ('TextArea6', 'INPUT_TEXTAREA_TYPE', 'pair'),
    'PASSWORD':         ('Password23', 'INPUT_SECRET_TYPE', 'pair'),
    'HIDDEN':           ('HiddenTextBox7', 'HIDDEN_TYPE', 'pair'),
    'RADIO':            ('RadioButton15', 'SELECT_RADIO_TYPE', 'pair'),
    'CHECKBOX':         ('CheckBox16', 'SELECT_CHECK_TYPE', 'pair'),
    'DROPDOWN':         ('Dropdown17', 'SELECT_COMBO_TYPE', 'pair'),
    'SELECT':           ('Dropdown17', 'SELECT_COMBO_TYPE', 'pair'),
    'LISTBOX':          ('ListBox18', 'SELECT_LIST_TYPE', 'pair'),
    'DATE':             ('Date19', 'DIALOG_DATE', 'pair'),
    'DATETIME':         ('Date19', 'DIALOG_DATETIME', 'pair'),
    'TIME':             ('Time20', 'DIALOG_TIME', 'pair'),
    'BUTTON':           ('Button4', '', 'caption'),
    'ATTACHMENT':       ('Attachment', '', 'caption'),
    'LINK':             ('Link25', '', 'pair_caption'),
    'SERIAL_NUMBER':    ('SerialNumber9', '', 'pair'),
    'TITLE':            ('Title1', '', 'pair'),
    'LABEL':            ('Label3', '', 'own'),
    'HORIZONTAL_LINE':  ('HorizontalLine2', '', 'none'),
    'IMAGE':            ('Image24', '', 'none'),
    'BARCODE':          ('Barcode26', 'Codabar', 'pair'),
    'QRCODE':           ('QRCode27', '', 'none'),
    'HANDWRITING':      ('HandWriting28', '', 'pair'),
    'DIALOGINPUT':      ('DialogInput11', 'DIALOG_INPUT', 'pair'),
    'DIALOGINPUTLABEL': ('DialogInputLabel12', 'DIALOG_INPUT_LABEL', 'pair'),
    'DIALOGINPUTMULTI': ('DialogInputMulti13', 'DIALOG_INPUT_MULTI', 'pair'),
    'DOUBLETEXT':       ('DoubleTextBox14', '', 'pair'),
}
# 明確做不到的型別。做不到就說做不到，不要產出一個看起來對、匯進去才壞的檔案
UNSUPPORTED_TYPES = {
    'LIST': '表格明細：listItems 內每一欄都要另外繫結一個輸入元件，本工具尚未做。'
            '要明細請走 build_form.py，或匯入後在設計器補',
    'SUBTAB': '分頁：rwdLayout 的 tabs 結構尚未做。匯入後在設計器補',
}
# 選項型別：沒有 options 就等於做出一個永遠選不到東西的欄位
OPTION_TYPES = ('RADIO', 'CHECKBOX', 'DROPDOWN', 'SELECT', 'LISTBOX')
# TITLE 的配對標籤要用教材檔的標題標籤（22px、置中），用一般欄位標籤會變成小字
LABEL_FRAGMENTS = {'TITLE': 'lbl_Title1'}

# IR 7.4 的保留 ID：改了不會報錯，是匯入後功能失效才發現
RESERVED_IDS = {'ATTACHMENT': 'Attachment', 'SERIAL_NUMBER': 'SerialNumber'}

# 關卡型別 → 從哪一份檔案的哪一個關卡複製
ACTIVITY_SOURCES = {
    'StartEvent': ('blank', 'StartEvent_1'),
    'EndEvent':   ('blank', 'EndEvent_2'),
    'UserTask':   ('blank', 'UserTask_3'),
    'SendTask':   ('library', 'ACT_SendNotify_01'),
}
# 空白範本只帶這兩種執行者，兩種都已隨範本匯入過。其他型別（部門主管、表單欄位指定…）
# 的 XML 寫法沒有實測過，一律擋下來請人在設計器指定（AGENTS.md 第 6 節）
PARTICIPANT_TYPES = ('PROCESS_REQUESTER', 'MANAGER')
# 有簽核者的關卡才要掛執行者
PERFORMER_TYPES = ('UserTask', 'SendTask')

# 以下三段樣板逐字取自 templates/原始空白專案 的實際內容，只把會變的格子挖成 %(…)s。
# 不自己拼標籤 —— 手拼漏一格（例如 SelectItem 漏 itemValue）設計器會直接開不起來。
_TRANSITION_REF_TMPL = '''<com.dsc.nana.domain.workflow__definition.TransitionReference>
                  <containerOID>%(container)s</containerOID>
                  <transitionDefinitionId>%(link)s</transitionDefinitionId>
                  <SET__PROXY__CLASS__NAME>org.apache.ojb.broker.accesslayer.SetProxy</SET__PROXY__CLASS__NAME>
                  <LIST__PROXY__CLASS__NAME>org.apache.ojb.broker.accesslayer.ListProxy</LIST__PROXY__CLASS__NAME>
                  <OID>%(oid)s</OID>
                  <objectVersion>1</objectVersion>
                  <dto>true</dto>
                  <dtoState reference="../../../../../../../../../header/dtoState"/>
                </com.dsc.nana.domain.workflow__definition.TransitionReference>'''

_TRANSITION_TMPL = '''<com.dsc.nana.domain.workflow__definition.TransitionDefinition>
          <container class="com.dsc.nana.domain.workflow_definition.ProcessDefinition" reference="../../.."/>
          <fromActivityDefinitionId>%(source)s</fromActivityDefinitionId>
          <id>%(link)s</id>
          <name>%(name)s</name>
          <toActivityDefinitionId>%(target)s</toActivityDefinitionId>
          <SET__PROXY__CLASS__NAME>org.apache.ojb.broker.accesslayer.SetProxy</SET__PROXY__CLASS__NAME>
          <LIST__PROXY__CLASS__NAME>org.apache.ojb.broker.accesslayer.ListProxy</LIST__PROXY__CLASS__NAME>
          <OID>%(oid)s</OID>
          <objectVersion>1</objectVersion>
          <dto>true</dto>
          <dtoState reference="../../../../../header/dtoState"/>
        </com.dsc.nana.domain.workflow__definition.TransitionDefinition>'''

_DIAGRAM_HEAD = '''<?xml version="1.0" encoding="UTF-8"?>
<Diagram x="0.0" y="0.0" width="%(width).1f" height="1050.0">
'''
_DIAGRAM_EVENT = '''<Node ClassName="%(type)s" Id="%(id)s">
<Font name="微軟正黑體" style="0" size="15"></Font>
<Bounds x="%(x).1f" y="100.0" width="30.0" height="30.0"></Bounds>
<ZIndex>3</ZIndex>
<Background Red="220" Green="230" Blue="242"></Background>
<Text></Text>
<TextBrush Red="0" Green="0" Blue="0"></TextBrush>
<ContainerNode NodeId="%(id)s">NoContainerNode</ContainerNode>
</Node>
'''
_DIAGRAM_TASK = '''<Node ClassName="%(type)s" Id="%(id)s">
<Font name="微軟正黑體" style="0" size="10"></Font>
<Bounds x="%(x).1f" y="90.0" width="80.0" height="50.0"></Bounds>
<ZIndex>3</ZIndex>
<Background Red="220" Green="230" Blue="242"></Background>
<Text>%(name)s</Text>
<TextBrush Red="0" Green="0" Blue="0"></TextBrush>
<ContainerNode NodeId="%(id)s">NoContainerNode</ContainerNode>
</Node>
'''
_DIAGRAM_LINK = '''<Node ClassName="DiagramLink" Id="%(link)s">
<Bounds x="%(x).1f" y="115.0" width="%(width).1f" height="0.0"></Bounds>
<ZIndex>5</ZIndex>
<Background Red="0" Green="0" Blue="0"></Background>
<Form Id="%(source)s">%(sourceType)s</Form>
<To Id="%(target)s">%(targetType)s</To>
<Text></Text>
<LinkShape>2</LinkShape>
<PointList>
<Point x="%(x)d" y="115"></Point>
<Point x="%(x2)d" y="115"></Point>
</PointList>
<ContainerNode NodeId="NoNodeId">NoContainerNode</ContainerNode>
</Node>
'''


def _load(path):
    return json.loads(io.open(path, encoding='utf-8').read())


def _oid_base(seed):
    """依表單／流程代號決定 OID 前綴的起算值，每個專案配 4096 個號。"""
    h = int(hashlib.md5(seed.encode('utf-8')).hexdigest()[:4], 16)
    return OID_BASE + h * 0x1000


class _Oids(object):
    """組裝期間的 OID 配號器。最後還會整份重配一次，這裡只要保證互不重複。"""

    def __init__(self):
        self.n = 0

    def next(self):
        self.n += 1
        return '%08x' % (WORK_BASE + self.n) + WORK_SUFFIX


# ---------------------------------------------------------------- 校驗

def check_form_ir(form_ir):
    """IR 的表單部分。錯的欄位 ID 不會讓匯入失敗，是執行期才炸，所以先擋。"""
    problems = []
    for key in ('formId', 'formName'):
        if not form_ir.get(key):
            problems.append('form_ir 缺少 %s' % key)
    if form_ir.get('formId') and not ID_RE.match(form_ir['formId']):
        problems.append('formId「%s」不合法：只允許英數字與底線、不可數字開頭'
                        % form_ir['formId'])

    seen = set()
    for field in form_ir.get('fields') or []:
        fid = field.get('id') or ''
        ftype = (field.get('type') or '').upper()
        if not ID_RE.match(fid):
            problems.append('欄位 ID「%s」不合法：只允許英數字與底線、不可數字開頭'
                            '（ID 會被當成 XML 標籤名寫進欄位權限字串）' % fid)
            continue
        if fid in seen:
            problems.append('欄位 ID 重複：%s' % fid)
        seen.add(fid)
        if ftype in UNSUPPORTED_TYPES:
            problems.append('欄位 %s 的型別 %s 目前不支援 —— %s'
                            % (fid, ftype, UNSUPPORTED_TYPES[ftype]))
        elif ftype not in ELEMENT_TYPES:
            problems.append('欄位 %s 的型別「%s」不在型別表內，可用的是：%s'
                            % (fid, ftype, '、'.join(sorted(ELEMENT_TYPES))))
        if ftype in OPTION_TYPES and not field.get('options'):
            problems.append('欄位 %s 是 %s，必須有 options' % (fid, ftype))
        if ftype in RESERVED_IDS and fid != RESERVED_IDS[ftype]:
            problems.append('欄位 %s 是 %s，ID 必須叫 %s（保留 ID，改名會讓內建功能失效）'
                            % (fid, ftype, RESERVED_IDS[ftype]))
        if ftype == 'BUTTON' and not re.search(r'(?i)(button|btn)$', fid):
            problems.append('按鈕 %s 的 ID 必須以 Button 或 Btn 結尾，'
                            '否則權限矩陣會把它當一般欄位' % fid)
    return problems


def check_process_ir(process_ir, field_ids):
    """IR 的流程部分：型別、執行者、連線、權限引用的欄位是否真的存在。"""
    problems = []
    for key in ('processId', 'processName'):
        if not process_ir.get(key):
            problems.append('process_ir 缺少 %s' % key)
    if process_ir.get('processId') and not ID_RE.match(process_ir['processId']):
        problems.append('processId「%s」不合法' % process_ir['processId'])

    ids, starts, ends = [], 0, 0
    for act in process_ir.get('activities') or []:
        aid = act.get('id') or ''
        atype = act.get('type') or ''
        if not ID_RE.match(aid):
            problems.append('關卡 ID「%s」不合法' % aid)
            continue
        if aid in ids:
            problems.append('關卡 ID 重複：%s' % aid)
        ids.append(aid)
        if atype not in ACTIVITY_SOURCES:
            problems.append('關卡 %s 的型別「%s」不支援，可用的是：%s'
                            % (aid, atype, '、'.join(sorted(ACTIVITY_SOURCES))))
            continue
        starts += atype == 'StartEvent'
        ends += atype == 'EndEvent'
        participant = act.get('participant') or 'PROCESS_REQUESTER'
        if atype in PERFORMER_TYPES and participant not in PARTICIPANT_TYPES:
            problems.append('關卡 %s 的執行者「%s」本工具產不出來，只能是 %s；'
                            '其他型別請匯入後在設計器指定'
                            % (aid, participant, '／'.join(PARTICIPANT_TYPES)))
        for fid, value in (act.get('permissions') or {}).items():
            if fid not in field_ids:
                problems.append('關卡 %s 的權限欄位 %s 在表單裡不存在' % (aid, fid))
            if value not in bpm_edit.PERMISSION_VALUES:
                problems.append('關卡 %s 的權限值「%s」不合法（欄位 %s）；只有 %s，'
                                '唯讀的作法是不要列出這個欄位'
                                % (aid, value, fid, '／'.join(bpm_edit.PERMISSION_VALUES)))
        if atype not in ('UserTask',) and act.get('permissions'):
            problems.append('關卡 %s 是 %s，設欄位權限沒有意義（沒有人會開這張表單）'
                            % (aid, atype))
    if starts != 1:
        problems.append('必須剛好一個 StartEvent，目前 %d 個' % starts)
    if ends < 1:
        problems.append('至少要有一個 EndEvent')

    outgoing = {}
    for link in process_ir.get('transitions') or []:
        source, target = link.get('from'), link.get('to')
        for end in (source, target):
            if end not in ids:
                problems.append('連線 %s → %s 指到不存在的關卡 %s'
                                % (source, target, end))
        outgoing.setdefault(source, []).append(target)

    # 走一次圖：起點到不了終點的流程，匯進去也跑不動
    if starts == 1 and not problems:
        start = [a['id'] for a in process_ir['activities'] if a['type'] == 'StartEvent'][0]
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(outgoing.get(cur, []))
        unreachable = [i for i in ids if i not in seen]
        if unreachable:
            problems.append('從 %s 走不到這些關卡：%s' % (start, '、'.join(unreachable)))
        dead = [a['id'] for a in process_ir['activities']
                if a['type'] != 'EndEvent' and not outgoing.get(a['id'])]
        if dead:
            problems.append('這些關卡沒有出線，流程會停在那裡：%s' % '、'.join(dead))
    return problems


# ---------------------------------------------------------------- 表單

def ir_to_fields(form_ir):
    """把 IR 的欄位翻成 build_from_online.build_element 吃的形狀。"""
    fields = []
    for field in form_ir.get('fields') or []:
        ftype = (field.get('type') or '').upper()
        fragment, control_type, slot = ELEMENT_TYPES[ftype]
        label = field.get('label') or ''
        options = [(o.get('caption', ''), o.get('value', ''))
                   for o in (field.get('options') or [])]
        fields.append({
            'id': field['id'],
            'irType': ftype,
            'fragment': fragment,
            'labelFragment': LABEL_FRAGMENTS.get(ftype),
            'cls': '',                      # 讀完教材檔才知道，build() 補
            'controlType': control_type,
            'label': label,
            'caption': label if slot in ('caption', 'pair_caption') else '',
            'ownText': label if slot == 'own' else '',
            'options': options,
            'required': bool(field.get('required')),
            'hint': field.get('hint') or '',
            'layout': field.get('layout') or {},
            # 隱藏欄的 label 通常是空的，但配對標籤還是要有（見 ELEMENT_TYPES 的說明），
            # 標籤文字沒給就用欄位 ID —— 反正隱藏欄不進版面，畫面上看不到
            'hasLabel': slot in ('pair', 'pair_caption'),
            'top': 0,
            'left': 0,
        })
    return fields


def ir_to_layout(fields):
    """把 IR 的 row / col / span 換成 rwdLayout 的 12 欄格線。

    隱藏欄位一律不進版面 —— 放進格線畫面不會畫它，
    腳本 document.getElementById 就抓不到（build_from_online.build_rwd_layout 同理）。
    標題與分隔線是整列型，用 rowType 表示，不佔格子。
    """
    placed = [f for f in fields if f['irType'] != 'HIDDEN']
    numbered = [f for f in placed if f['layout'].get('row')]
    tail = [f for f in placed if not f['layout'].get('row')]
    next_row = max([f['layout']['row'] for f in numbered] or [0])
    for field in tail:
        next_row += 1
        field['layout'] = dict(field['layout'], row=next_row, col=1, span=12)

    rows = {}
    for field in placed:
        rows.setdefault(field['layout']['row'], []).append(field)

    layout, problems = [], []
    for number in sorted(rows):
        members = sorted(rows[number], key=lambda f: f['layout'].get('col', 1))
        row_types = [f for f in members if f['irType'] in ('TITLE', 'HORIZONTAL_LINE')]
        if row_types:
            if len(members) > 1:
                problems.append('第 %d 列的 %s 是整列型元件，不能與其他欄位同列'
                                % (number, row_types[0]['id']))
            kind = 'Title' if row_types[0]['irType'] == 'TITLE' else 'HorizontalLine'
            layout.append({'rowType': kind, 'id': row_types[0]['id']})
            continue

        widths = [int(f['layout'].get('span') or 12 // len(members)) for f in members]
        total = sum(widths)
        if total > 12:
            problems.append('第 %d 列的 span 加總 %d 超過 12 欄：%s'
                            % (number, total, '、'.join(f['id'] for f in members)))
            continue
        cells = [[{'id': f['id']}] for f in members]
        if total < 12:                      # 補一格空的把 12 欄填滿，與教材檔的寫法一致
            widths.append(12 - total)
            cells.append([{}])
        layout.append({'row': widths,
                       'column': [[12]] * len(widths),
                       'elements': cells})
    return layout, problems


def build_script(form_ir):
    """產生表單 JavaScript：五個生命週期函式 + IR 列到的事件函式空殼。

    只給殼，不寫業務邏輯 —— 那是人要填的（PLAN.md 第 3 節 script_builder 的分工）。
    """
    hooks = form_ir.get('script', {}).get('hooks') \
        or ['formCreate', 'formOpen', 'formSave', 'formClose', 'formDispatch']
    parts = ['function %s(){\n  return true;\n}' % h for h in hooks]
    for event in form_ir.get('script', {}).get('events') or []:
        parts.append('function %s_%s(){\n  // TODO：%s\n}'
                     % (event.get('field'), event.get('event'),
                        event.get('note') or '待補業務邏輯'))
    return '\n'.join(parts)


# ---------------------------------------------------------------- 流程

def _is_sibling_activity_ref(path):
    """指向『第一個 ActivityDefinition』的相對參照。

    XStream 的 XPATH 參照是位置相對的：`../../…ActivityDefinition/finishMode`
    指的是清單裡的第一個關卡。要複製、重排關卡，得先把這些參照展開成實體內容，
    否則搬動之後它們會指到別人身上（build_bpmn.py 的檔頭也記著同一件事）。
    """
    return 'ActivityDefinition' in path


def _read_activity_blocks():
    """讀出可複製的關卡片段，回傳 {關卡型別: 片段原文}。"""
    blocks = {}
    for tag, path in (('blank', BLANK_BPMN), ('library', LIBRARY_BPMN)):
        wanted = [(t, source) for t, (origin, source) in ACTIVITY_SOURCES.items()
                  if origin == tag]
        if not wanted:
            continue
        if not os.path.isfile(path):
            raise SystemExit('找不到關卡片段來源 %s' % path)
        text, _ = X.read_xml(path)
        text, _done, skipped = xstream_ref.inline_refs(text, _is_sibling_activity_ref)
        if skipped:
            raise SystemExit('%s 有 %d 個關卡參照展不開，複製關卡會指錯對象：%s'
                             % (os.path.basename(path), len(skipped), skipped[:3]))
        found = {}
        for span in X.find_blocks(text, lambda n: n == WF + 'ActivityDefinition'):
            found[X.child_text(text, span, 'id')] = text[span.start:span.end]
        for atype, source in wanted:
            if source not in found:
                raise SystemExit('%s 裡沒有 %s' % (os.path.basename(path), source))
            block = found[source]
            # 教材檔的關卡綁著它自己的表單，先改回空白範本的代號，
            # 後面的表單繫結替換才會一次改乾淨
            block = block.replace(LIBRARY_FORM_ID, BLANK_FORM_ID)
            blocks[atype] = block
    return blocks


def _read_participant_pattern():
    """空白範本的申請人執行者，拿來當所有執行者的樣板。"""
    text, _ = X.read_xml(BLANK_BPMN)
    for span in X.find_blocks(text, lambda n: n == WF + 'ParticipantDefinition'):
        if X.child_text(text, span, 'id') != '_SystemParticipantID':
            return text[span.start:span.end]
    raise SystemExit('空白範本裡找不到可當樣板的執行者')


def _system_participant():
    text, _ = X.read_xml(BLANK_BPMN)
    for span in X.find_blocks(text, lambda n: n == WF + 'ParticipantDefinition'):
        if X.child_text(text, span, 'id') == '_SystemParticipantID':
            return text[span.start:span.end]
    raise SystemExit('空白範本裡找不到 _SystemParticipantID')


def _set_top(block, tag, value):
    """換掉區塊最上層那一個 <tag> 的內容。

    不能用「第一個出現的」—— 關卡片段裡 Tool 也有一個 <id>，
    而且排在關卡自己的 <id> 前面，改錯會把應用程式定義的編號蓋掉。
    """
    root = X.find_blocks(block, lambda n: True)[0]
    node = X.child(block, root, tag)
    if node is None:
        raise SystemExit('片段缺少最上層的 <%s>' % tag)
    return X.apply_edits(block, [(node.inner_start, node.inner_end, value)])


def _fresh_oids(block, oids):
    """把片段內的 OID 全部換成新的一組。

    關卡片段的 containerOID 一律指向片段內部（實測空白範本與教材檔的 10 個關卡皆然），
    所以整段換掉不會扯斷對外的指向。
    """
    seen = []
    for m in re.finditer(r'<(OID|containerOID)>([0-9a-f]{32})</\1>', block):
        if m.group(2) not in seen:
            seen.append(m.group(2))
    for old in seen:
        block = block.replace(old, oids.next())
    return block


def _set_transition_refs(block, links, oids):
    """關卡的 transitionReferences 只列「從這一關出去」的連線。"""
    root = X.find_blocks(block, lambda n: True)[0]
    restrictions = X.child(block, root, 'transitionRestrictions')
    inner = X.find_blocks(block, lambda n: n == WF + 'TransitionRestriction',
                          restrictions.inner_start, restrictions.inner_end)
    if not inner:
        raise SystemExit('關卡片段裡沒有 TransitionRestriction')
    restriction = inner[0]
    container = X.child_text(block, restriction, 'OID')

    body = '\n                '.join(
        _TRANSITION_REF_TMPL % {'container': container, 'link': link,
                                'oid': oids.next()}
        for link in links)
    new = ('<transitionReferences>\n                %s\n              '
           '</transitionReferences>' % body) if links else ''

    existing = X.find_blocks(block, lambda n: n == 'transitionReferences',
                             restriction.inner_start, restriction.inner_end)
    if existing:
        return X.apply_edits(block, [(existing[0].start, existing[0].end, new)])
    if not links:
        return block
    return block[:restriction.inner_start] + '\n              ' + new \
        + block[restriction.inner_start:]


def _diagram(activities, transitions):
    """畫布：一條線由左至右排開。座標只影響設計師畫面，不影響執行。"""
    x, geometry, nodes = 100.0, {}, []
    for act in activities:
        width = 30.0 if act['type'] in ('StartEvent', 'EndEvent') else 80.0
        geometry[act['id']] = (x, width, act['type'])
        template = _DIAGRAM_EVENT if width == 30.0 else _DIAGRAM_TASK
        nodes.append(template % {'type': act['type'], 'id': act['id'], 'x': x,
                                 'name': X.xml_escape(act.get('name') or '')})
        x += width + 60.0

    for link in transitions:
        source_x, source_w, source_t = geometry[link['from']]
        target_x, _target_w, target_t = geometry[link['to']]
        nodes.append(_DIAGRAM_LINK % {
            'link': link['id'], 'x': source_x + source_w,
            'x2': target_x, 'width': target_x - source_x - source_w,
            'source': link['from'], 'sourceType': source_t,
            'target': link['to'], 'targetType': target_t})
    return (_DIAGRAM_HEAD % {'width': x + 100.0}) + ''.join(nodes) + '</Diagram>'


def _replace_inner(text, tag, inner):
    spans = X.find_blocks(text, lambda n: n == tag)
    if not spans:
        raise SystemExit('骨架裡找不到 <%s>' % tag)
    return X.apply_edits(text, [(spans[0].inner_start, spans[0].inner_end, inner)])


def build_bpmn(process_ir, form_id):
    """由空白範本組出流程檔，回傳 (XML, BOM, 訊息清單)。"""
    text, bom = X.read_xml(BLANK_BPMN)
    text, _done, skipped = xstream_ref.inline_refs(text, _is_sibling_activity_ref)
    if skipped:
        raise SystemExit('空白範本有 %d 個關卡參照展不開：%s' % (len(skipped), skipped[:3]))

    blocks = _read_activity_blocks()
    pattern = _read_participant_pattern()
    oids = _Oids()
    messages = []

    activities = process_ir['activities']
    transitions = []
    for index, link in enumerate(process_ir.get('transitions') or [], 1):
        transitions.append({'id': 'Link_%d' % (len(activities) + index),
                            'from': link['from'], 'to': link['to'],
                            'name': link.get('name') or ''})

    outgoing = {}
    for link in transitions:
        outgoing.setdefault(link['from'], []).append(link['id'])

    act_parts, participant_parts = [], [_system_participant()]
    for index, act in enumerate(activities, 1):
        block = blocks[act['type']]
        block = _set_top(block, 'id', act['id'])
        block = _set_top(block, 'name', X.xml_escape(act.get('name') or ''))
        if act['type'] in PERFORMER_TYPES:
            participant_id = 'PAR%d%03d' % (WORK_BASE, index)
            ptype = act.get('participant') or 'PROCESS_REQUESTER'
            block = _set_top(block, 'performerIds', participant_id)
            participant = _set_top(pattern, 'id', participant_id)
            participant = re.sub(r'(<type>\s*<value>)[^<]*(</value>)',
                                 lambda m: m.group(1) + ptype + m.group(2),
                                 participant, count=1)
            # 執行者的 containerOID 指向流程定義（在片段外面），只能換自己的 OID
            participant = _set_top(participant, 'OID', oids.next())
            participant_parts.append(participant)
            messages.append('%s（%s）執行者 %s' % (act['id'], act['type'], ptype))
        block = _set_transition_refs(block, outgoing.get(act['id'], []), oids)
        block = _fresh_oids(block, oids)
        act_parts.append(block)

    link_parts = []
    for link in transitions:
        link_parts.append(_TRANSITION_TMPL % {
            'source': link['from'], 'target': link['to'], 'link': link['id'],
            'name': X.xml_escape(link['name']), 'oid': oids.next()})

    text = _replace_inner(text, 'activityDefinitions',
                          '\n        %s\n      ' % '\n        '.join(act_parts))
    text = _replace_inner(text, 'transitionDefinitions',
                          '\n        %s\n      ' % '\n        '.join(link_parts))
    text = _replace_inner(text, 'participantDefinitions',
                          '\n        %s\n      ' % '\n        '.join(participant_parts))
    text = _replace_inner(text, 'bpmXML',
                          X.xml_escape(_diagram(activities, transitions)))
    # 設計師靠這個計數器決定下一個自動編號，留著範本的 7 會與我們產的 Link_N 撞號
    text = _replace_inner(text, 'lastActivityIdNum',
                          str(len(activities) + len(transitions) + 1))

    # 流程包／流程定義的識別字
    text, n_id = bpm_edit.replace_leaf(text, 'id', BLANK_PROCESS_ID,
                                       process_ir['processId'])
    text, n_main = bpm_edit.replace_leaf(text, 'mainProcessDefinitionId',
                                         BLANK_PROCESS_ID, process_ir['processId'])
    text, n_name = bpm_edit.replace_leaf(text, 'name', BLANK_PROCESS_NAME,
                                         X.xml_escape(process_ir['processName']))
    if (n_id, n_main, n_name) != (2, 1, 2):
        raise SystemExit('流程識別字的處數與預期不符（id=%d, main=%d, name=%d）'
                         % (n_id, n_main, n_name))

    # 表單繫結：關卡是靠 relevantDataDefinitionId 找到表單的，一處都不能漏
    bound = 0
    for tag in ('formDefinitionId', 'relevantDataDefinitionId', 'id', 'name'):
        text, n = bpm_edit.replace_leaf(
            text, tag, BLANK_FORM_ID,
            X.xml_escape(process_ir['processName']) if tag == 'name' else form_id)
        bound += n
    messages.append('表單繫結 %d 處（流程變數 + 每個任務關卡各一處）' % bound)
    # 少改一處就靜默綁不到表單，所以不數處數，直接確認範本識別字沒有殘留
    for leftover in (BLANK_FORM_ID, BLANK_PROCESS_ID, BLANK_PROCESS_NAME):
        if leftover in text:
            raise SystemExit('範本識別字「%s」還留在流程檔裡，表單或流程會綁錯' % leftover)

    for act in activities:
        if act.get('permissions'):
            text = bpm_edit.set_field_permissions(text, act['id'], form_id,
                                                  act['permissions'])
            messages.append('%s 欄位權限 %d 項' % (act['id'], len(act['permissions'])))

    text, n_oid = bpm_edit.remap_oids(
        text, _oid_base(form_id + process_ir['processId']), OID_SUFFIX)
    messages.append('OID 重配 %d 個' % n_oid)
    return text, bom, messages


# ---------------------------------------------------------------- 驗證

def verify_bpmn(path, process_ir):
    """反解產出的 .bpmn，與 IR 逐項對比（PLAN.md 的 L1）。"""
    data = bpmn_handler.extract(path)
    produced = {a['id']: a for a in data['activities']}
    good = True

    print('  反解得到 %d 個關卡，預期 %d 個'
          % (len(produced), len(process_ir['activities'])))
    for act in process_ir['activities']:
        got = produced.get(act['id'])
        if got is None:
            print('  [失敗] 產出裡沒有關卡 %s' % act['id'])
            good = False
            continue
        if got['type'] != act['type']:
            print('  [失敗] %s 的型別是 %s，IR 寫的是 %s'
                  % (act['id'], got['type'], act['type']))
            good = False
        expected = act.get('permissions') or {}
        actual = dict([(item['id'], item['permission'])
                       for item in got['buttons'] + got['fieldPermissions']])
        if expected != actual:
            print('  [失敗] %s 的欄位權限與 IR 不符：少了 %s，多了 %s'
                  % (act['id'],
                     sorted(set(expected) - set(actual)) or '無',
                     sorted(set(actual) - set(expected)) or '無'))
            good = False

    text, _ = X.read_xml(path)
    links = []
    for span in X.find_blocks(text, lambda n: n == WF + 'TransitionDefinition'):
        links.append((X.child_text(text, span, 'fromActivityDefinitionId'),
                      X.child_text(text, span, 'toActivityDefinitionId')))
    expected_links = [(t['from'], t['to']) for t in process_ir.get('transitions') or []]
    print('  連線 %d 條，預期 %d 條' % (len(links), len(expected_links)))
    if sorted(links) != sorted(expected_links):
        print('  [失敗] 連線與 IR 不符：%s' % (set(expected_links) ^ set(links)))
        good = False

    # 流程圖節點與關卡必須一一對應，否則設計師畫布會少東西或指到不存在的關卡
    diagram = X.xml_unescape(
        re.search(r'<bpmXML>(.*?)</bpmXML>', text, re.S).group(1))
    drawn = set(re.findall(r'<Node ClassName="(?!DiagramLink)[^"]+" Id="([^"]+)">', diagram))
    missing = set(produced) - drawn
    if missing:
        print('  [失敗] 流程圖少畫了：%s' % '、'.join(sorted(missing)))
        good = False
    return good


def verify_form(path, fields):
    """反解產出的 .form，與 IR 的欄位逐項對比。"""
    result = form_handler.extract(path)
    produced = dict([(f['id'], f) for f in result.get('fields', [])])
    expected = [f for f in fields]
    print('  反解得到 %d 個欄位，預期 %d 個' % (len(produced), len(expected)))
    good = True
    for field in expected:
        got = produced.get(field['id'])
        if got is None:
            print('  [失敗] 產出裡沒有欄位 %s' % field['id'])
            good = False
            continue
        want = field['label']
        if want and got.get('displayName') and got['displayName'] != want:
            print('  [注意] %s 的中文名反解成「%s」，IR 寫的是「%s」'
                  % (field['id'], got['displayName'], want))
    return good


# ---------------------------------------------------------------- 主流程

def main(argv=None):
    parser = argparse.ArgumentParser(
        description='由 AI 產出的 IR 組出可匯入的 .form / .js / .bpmn')
    parser.add_argument('--form-ir', required=True, help='form_ir.json')
    parser.add_argument('--process-ir', default=None, help='process_ir.json；不給就只產表單')
    parser.add_argument('--script', default=None,
                        help='表單 JavaScript 檔；不給就依 IR 的 script 段產生函式空殼')
    parser.add_argument('--out', required=True, help='輸出目錄')
    args = parser.parse_args(argv)

    form_ir = _load(args.form_ir)
    process_ir = _load(args.process_ir) if args.process_ir else None

    print('校驗 IR')
    problems = check_form_ir(form_ir)
    field_ids = set([f.get('id') for f in form_ir.get('fields') or []])
    if process_ir:
        problems += check_process_ir(process_ir, field_ids)
        if process_ir.get('formId') and process_ir['formId'] != form_ir.get('formId'):
            problems.append('process_ir 的 formId「%s」與 form_ir 的「%s」不一致'
                            % (process_ir['formId'], form_ir['formId']))
    if problems:
        for problem in problems:
            print('  [失敗] %s' % problem)
        raise SystemExit('IR 有 %d 個問題，一項都沒組裝。'
                         '（ID 打錯不會讓匯入失敗，是執行期才炸，所以先擋下來）'
                         % len(problems))
    print('  表單 %d 個欄位、流程 %d 個關卡，全部通過'
          % (len(field_ids), len(process_ir['activities']) if process_ir else 0))

    fields = ir_to_fields(form_ir)
    layout, layout_problems = ir_to_layout(fields)
    if layout_problems:
        for problem in layout_problems:
            print('  [失敗] %s' % problem)
        raise SystemExit('版面有問題，未組裝')

    library, _item = online.read_library()
    for field in fields:
        field['cls'] = library[field['fragment']][0]

    script = io.open(args.script, encoding='utf-8').read() if args.script \
        else build_script(form_ir)

    print('組裝表單（骨架＝原始空白專案，元件＝快速開發測試教材檔）')
    text, bom, messages, built = online.build_form(
        fields, form_ir['formId'], form_ir['formName'], script, script, layout=layout)
    for message in messages:
        print('  ' + message)

    out_dir = os.path.abspath(args.out)
    folders = [os.path.join(out_dir, '表單')]
    if process_ir:
        folders.append(os.path.join(out_dir, '流程'))
    for folder in folders:
        if not os.path.isdir(folder):
            os.makedirs(folder)
    form_out = os.path.join(out_dir, '表單', form_ir['formId'] + '.form')
    X.write_xml(form_out, text, bom)
    io.open(os.path.join(out_dir, '表單', form_ir['formId'] + '.js'),
            'w', encoding='utf-8', newline='').write(script)
    print('  產出 %s（版面 %d 列）' % (os.path.relpath(form_out, out_dir), len(layout)))

    good = True
    print('驗證表單（反解對比，PLAN.md 的 L1）')
    good = verify_form(form_out, built) and good
    good = online.check_layout_ids(form_out) and good
    good = online.check_select_items(form_out) and good
    good = online.check_pair_ids(form_out) and good
    good = online.check_designer_load(form_out) and good

    if process_ir:
        print('組裝流程（骨架＝原始空白專案，通知關卡＝教材檔）')
        bpmn_text, bpmn_bom, bpmn_messages = build_bpmn(process_ir, form_ir['formId'])
        for message in bpmn_messages:
            print('  ' + message)
        bpmn_out = os.path.join(out_dir, '流程', process_ir['processId'] + '.bpmn')
        X.write_xml(bpmn_out, bpmn_text, bpmn_bom)
        print('  產出 %s' % os.path.relpath(bpmn_out, out_dir))

        print('驗證流程（反解對比）')
        good = verify_bpmn(bpmn_out, process_ir) and good

    print()
    if good:
        print('組裝完成。這是 L1 通過，匯入設計師（L2）與實跑一張單（L3）仍須人工。')
    else:
        print('組裝完成，但反解對比有落差 —— 匯入前先處理上面標 [失敗] 的項目。')
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
