# -*- coding: utf-8 -*-
"""由 samples/快速開發測試 的教材表單，組出「AI設計的流程測試」的 .form。

作法刻意保守（見 ../PLAN.md 第 7 節）：不憑空生成 XML，
一律以一份確定能匯入的既有檔案為底，只做四件事——
    1. 展開 XStream 的數字 reference（展開後才能安全增刪元件與重編號）
    2. 改元件 ID 與中文名稱（走 1_xml_tool 已有測試保護的 write_back）
    3. 新增表格明細欄位所需的元件與 ListItem
    4. 全檔重編 XStream id、換掉表單 ID／名稱／OID／腳本

執行：python 8_BPMAIworker/tools/build_form.py
"""

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

SRC = os.path.join(ROOT, 'samples', '快速開發測試', '表單', '原檔案-quickDevTestForm.form')
OUT_DIR = os.path.join(ROOT, 'samples', 'AI設計的流程測試', '表單')

FORM_ID = 'AIDesignTestForm'
FORM_NAME = 'AI設計的流程測試'
# 32 碼 OID：前 8 碼遞增、後 24 碼固定（規則見 ../docs/流程生成手冊.md 第 3 節）
OID_SUFFIX = 'a1de51000851cac97a977dbbf'[:24]
FORM_CONTAINER_OID = '7a10c001' + OID_SUFFIX
FORM_OID = '7a10c002' + OID_SUFFIX

# 原 ID -> (新 ID, 中文名稱)。Attachment 與 SubTab22 刻意不改：
#   Attachment 疑似為系統保留的附件區代號；SubTab22 的頁籤 ListItem 是
#   SubTab22_0 / SubTab22_1，改父層 ID 會讓子頁籤 ID 對不上。
RENAMES = [
    ('HiddenTextBox7',     'processInstOIDHidden',   '流程實例ID'),
    ('Title1',             'FormTitle',              'AI設計的流程測試'),
    ('HorizontalLine2',    'TitleLine',              '分隔線'),
    ('Label3',             'FormNoteLabel',          '本單為 AI 產生的測試單，僅供功能驗證'),
    ('Button4',            'UploadFileButton',       '檔案上傳'),
    ('TextBox5',           'SubjectTextBox',         '主旨'),
    ('TextArea6',          'ContentTextArea',        '內容說明'),
    ('SerialNumber9',      'SerialNumber',           '單號'),
    ('Grid10',             'ItemGrid',               '明細表格'),
    ('DialogInput11',      'RelatedNoDialogInput',   '相關單號'),
    ('DialogInputLabel12', 'EmpDialogInputLabel',    '申請人（工號／姓名）'),
    ('DialogInputMulti13', 'RemarkDialogInputMulti', '備註'),
    ('DoubleTextBox14',    'DeptDoubleTextBox',      '部門（代號／名稱）'),
    ('RadioButton15',      'UrgencyRadio',           '急件等級'),
    ('CheckBox16',         'NotifyCheckBox',         '通知對象'),
    ('Dropdown17',         'CategoryDropDown',       '申請類別'),
    ('ListBox18',          'SiteListBox',            '廠區'),
    ('Date19',             'NeedDate',               '需求日期'),
    ('Time20',             'NeedTime',               '需求時間'),
    ('Password23',         'PasswordTextBox',        '密碼'),
    ('Image24',            'LogoImage',              '圖片'),
    ('Link25',             'RefLink',                '參考連結'),
    ('Barcode26',          'FormBarcode',            '條碼'),
    ('QRCode27',           'FormQRCode',             'QRCode'),
    ('HandWriting28',      'SignHandWriting',        '手寫簽名'),
]

# 表格明細的三個欄位：(繫結欄位 ID, 中文欄名)
GRID_COLUMNS = [
    ('ItemNoTextBox',   '項次'),
    ('ItemNameTextBox', '品名'),
    ('ItemQtyTextBox',  '數量'),
]

# 樣板只有一顆按鈕，另外複製一顆出來：(新按鈕 ID, 按鈕文字)
EXTRA_BUTTONS = [
    ('PickUserButton', '帶入部門與人員'),
]

# 表格欄位用的輸入元件樣板（結構取自線上表單 SolarEnergyECRECN 的表格欄位）
_COL_ELEMENT_TMPL = '''<elementDefinition class="com.dsc.nana.domain.form.InputElementDefinition" id="900">
            <controlType id="900">
              <value>INPUT_TYPE</value>
            </controlType>
            <isRequired>false</isRequired>
            <isValidateDataType>false</isValidateDataType>
            <isValidateDataLength>false</isValidateDataLength>
            <isValidateDataRequire>false</isValidateDataRequire>
            <participantDefine id="900">
              <value>NORMAL</value>
            </participantDefine>
            <isReplaceThousandths>false</isReplaceThousandths>
            <isThousandths>false</isThousandths>
            <isCustomValidation>false</isCustomValidation>
            <computeFieldRule></computeFieldRule>
            <computeDateRule></computeDateRule>
            <computeGridRule></computeGridRule>
            <decimalPlaces></decimalPlaces>
            <storeDecimalPointModus>ACTUAL_VALUE</storeDecimalPointModus>
            <numChangeTextTW>false</numChangeTextTW>
            <numChangeTextCN>false</numChangeTextCN>
            <numChangeTextTWBinding></numChangeTextTWBinding>
            <numChangeTextCNBinding></numChangeTextCNBinding>
            <length>0</length>
            <textValue></textValue>
            <dataType id="900">
              <value>0</value>
            </dataType>
            <sqlCmdId></sqlCmdId>
            <pairId></pairId>
            <isHideLabel>false</isHideLabel>
            <labelAlign>0</labelAlign>
            <cssStyle></cssStyle>
            <cssDevice id="900">
              <value>0</value>
            </cssDevice>
            <description></description>
            <elementStyles class="list" id="900"/>
            <hint></hint>
            <id>__COLELEM__</id>
            <multiZhMap id="900"/>
            <name>__COLELEM__</name>
            <navindex>0</navindex>
            <precision>0</precision>
            <scale>0</scale>
            <persistentType>0</persistentType>
            <doValidationOnSubmit>false</doValidationOnSubmit>
            <isThesameId>true</isThesameId>
            <validationRules class="list" id="900"/>
          </elementDefinition>'''

_LIST_ITEM_TMPL = '''        <com.dsc.nana.domain.form.ListItem id="900">
          <itemOrder>__ORDER__</itemOrder>
          <id>__BIND__</id>
          <binding>__BIND__</binding>
          __ELEMENT__
          <caption>__CAPTION__</caption>
          <multiZhMap id="900"/>
          <hidden>false</hidden>
        </com.dsc.nana.domain.form.ListItem>
'''


def _add_grid_columns(text):
    """在 ItemGrid 的 <listItems> 內塞入三個欄位定義。"""
    grid = None
    for s in X.find_blocks(text, lambda n: n == 'com.dsc.nana.domain.form.ListElementDefinition'):
        if X.child_text(text, s, 'id') == 'ItemGrid':
            grid = s
            break
    if grid is None:
        raise ValueError('找不到 ItemGrid')

    li = X.child(text, grid, 'listItems')
    body = ''
    for order, (bind, caption) in enumerate(GRID_COLUMNS, 1):
        elem = _COL_ELEMENT_TMPL.replace('__COLELEM__', bind + 'Col')
        item = (_LIST_ITEM_TMPL
                .replace('__ORDER__', str(order))
                .replace('__BIND__', bind)
                .replace('__CAPTION__', caption)
                .replace('__ELEMENT__', elem))
        body += item
    new_li = '<listItems class="list" id="900">\n%s      </listItems>' % body
    return X.apply_edits(text, [(li.start, li.end, new_li)])


def _add_bound_elements(text):
    """新增表格欄位所繫結的三個輸入元件與其標籤。

    以既有的 SubjectTextBox（原 TextBox5）整段為樣板複製，只換 ID 與中文名，
    確保 40 個樣板子標籤與 elementStyles 完全比照既有可匯入的結構。
    """
    ctrl = lbl = None
    for s in X.find_blocks(text, lambda n: n.startswith('com.dsc.nana.domain.form.')
                           and n.endswith('ElementDefinition')):
        eid = X.child_text(text, s, 'id')
        if eid == 'SubjectTextBox':
            ctrl = s
        elif eid == 'lbl_SubjectTextBox':
            lbl = s
    if ctrl is None or lbl is None:
        raise ValueError('找不到樣板元件 SubjectTextBox / lbl_SubjectTextBox')

    ctrl_raw = text[ctrl.start:ctrl.end]
    lbl_raw = text[lbl.start:lbl.end]

    blocks = []
    for bind, caption in GRID_COLUMNS:
        c = (ctrl_raw
             .replace('<id>SubjectTextBox</id>', '<id>%s</id>' % bind)
             .replace('<name>SubjectTextBox</name>', '<name>%s</name>' % bind)
             .replace('<pairId>TextBox7</pairId>', '<pairId>%s</pairId>' % bind))
        l = (lbl_raw
             .replace('<id>lbl_SubjectTextBox</id>', '<id>lbl_%s</id>' % bind)
             .replace('<name>lbl_SubjectTextBox</name>', '<name>lbl_%s</name>' % bind)
             .replace('<pairId>TextBox7</pairId>', '<pairId>%s</pairId>' % bind))
        l, n_tv = re.subn(r'<textValue>.*?</textValue>',
                          '<textValue>%s</textValue>' % X.xml_escape(caption), l, count=1, flags=re.S)
        if '<id>%s</id>' % bind not in c:
            raise ValueError('元件樣板取代失敗（找不到 <id>SubjectTextBox</id>）：%s' % bind)
        if '<id>lbl_%s</id>' % bind not in l or n_tv != 1:
            raise ValueError('標籤樣板取代失敗：%s' % bind)
        blocks.append('    ' + l + '\n    ' + c + '\n')

    insert_at = ctrl.end
    text = text[:insert_at] + '\n' + ''.join(blocks).rstrip('\n') + text[insert_at:]

    # 再複製按鈕：樣板只有 UploadFileButton 一顆，另需一顆「帶入部門與人員」
    btn = None
    for s in X.find_blocks(text, lambda n: n == 'com.dsc.nana.domain.form.TriggerElementDefinition'):
        if X.child_text(text, s, 'id') == 'UploadFileButton':
            btn = s
            break
    if btn is None:
        raise ValueError('找不到樣板按鈕 UploadFileButton')
    btn_raw = text[btn.start:btn.end]
    add = []
    for bid, caption in EXTRA_BUTTONS:
        b = (btn_raw
             .replace('<id>UploadFileButton</id>', '<id>%s</id>' % bid)
             .replace('<name>UploadFileButton</name>', '<name>%s</name>' % bid))
        cap = re.search(r'<caption>.*?</caption>', b, re.S)
        b = b[:cap.start()] + '<caption>%s</caption>' % X.xml_escape(caption) + b[cap.end():]
        if '<id>%s</id>' % bid not in b:
            raise ValueError('按鈕樣板取代失敗：%s' % bid)
        add.append('    ' + b + '\n')
    return text[:btn.end] + '\n' + ''.join(add).rstrip('\n') + text[btn.end:]


def _patch_rwd_layout(text):
    """版面：把三個表格繫結欄位排成一列（3+3+3+3），插在明細表格那一列之前。"""
    span = X.find_blocks(text, lambda n: n == 'rwdLayout')[0]
    raw = X.xml_unescape(text[span.inner_start:span.inner_end])
    layout = json.loads(raw)

    row = {
        'row': [3, 3, 3, 3],
        'column': [[12], [12], [12], [12]],
        'elements': [[{'id': GRID_COLUMNS[0][0]}], [{'id': GRID_COLUMNS[1][0]}],
                     [{'id': GRID_COLUMNS[2][0]}], [{}]],
    }
    at = None
    for i, r in enumerate(layout):
        if json.dumps(r, ensure_ascii=False).find('"ItemGrid"') >= 0:
            at = i
            break
    if at is None:
        raise ValueError('rwdLayout 找不到 ItemGrid 那一列')
    layout.insert(at, row)

    # 新按鈕排在 UploadFileButton 右邊那一格
    placed = False
    for r in layout:
        if 'elements' not in r:
            continue
        for gi, cell in enumerate(r['elements']):
            if cell and cell[0].get('id') == 'UploadFileButton':
                nxt = gi + 1
                if nxt < len(r['elements']):
                    r['elements'][nxt] = [{'id': EXTRA_BUTTONS[0][0]}]
                    placed = True
                break
        if placed:
            break
    if not placed:
        raise ValueError('rwdLayout 找不到可放新按鈕的位置')

    new_raw = X.xml_escape(json.dumps(layout, ensure_ascii=False, separators=(',', ':')))
    return X.apply_edits(text, [(span.inner_start, span.inner_end, new_raw)])


def main():
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    out_path = os.path.join(OUT_DIR, FORM_ID + '.form')
    tmp = out_path + '.tmp'

    text, bom = X.read_xml(SRC)
    print('① 讀入樣板 %s（%d 字元）' % (os.path.basename(SRC), len(text)))

    text, n = bpm_edit.inline_numeric_refs(text)
    print('② 展開數字 reference %d 處' % n)
    X.write_xml(tmp, text, bom)

    cfg = {'fields': [{'originalId': o, 'id': n, 'name': t} for o, n, t in RENAMES]}
    changed, msgs = form_handler.write_back(tmp, cfg, tmp)
    print('③ 改名 %d 個元件' % changed)
    for m in msgs:
        print('   ' + m)

    text, _ = X.read_xml(tmp)
    text = _add_bound_elements(text)
    text = _add_grid_columns(text)
    text = _patch_rwd_layout(text)
    print('④ 新增 %d 個表格繫結元件、%d 個表格欄位定義、%d 顆按鈕'
          % (len(GRID_COLUMNS), len(GRID_COLUMNS), len(EXTRA_BUTTONS)))

    # 標籤文字：write_back 只改 ID，中文名要另外寫入
    hits = 0
    for old, new, caption in RENAMES:
        for s in X.find_blocks(text, lambda n: n == 'com.dsc.nana.domain.form.OutputElementDefinition'):
            if X.child_text(text, s, 'id') != 'lbl_' + new:
                continue
            tv = X.child(text, s, 'textValue')
            if tv is not None:
                text = X.apply_edits(text, [(tv.inner_start, tv.inner_end, X.xml_escape(caption))])
                hits += 1
            break
    # 沒有 lbl_ 標籤的（Label3 / 按鈕 / 標題）另外處理
    for eid, caption in (('FormNoteLabel', RENAMES[3][2]),):
        for s in X.find_blocks(text, lambda n: n == 'com.dsc.nana.domain.form.OutputElementDefinition'):
            if X.child_text(text, s, 'id') != eid:
                continue
            tv = X.child(text, s, 'textValue')
            text = X.apply_edits(text, [(tv.inner_start, tv.inner_end, X.xml_escape(caption))])
            hits += 1
            break
    for eid, caption in (('UploadFileButton', '檔案上傳'),):
        for s in X.find_blocks(text, lambda n: n == 'com.dsc.nana.domain.form.TriggerElementDefinition'):
            if X.child_text(text, s, 'id') != eid:
                continue
            cap = X.child(text, s, 'caption')
            text = X.apply_edits(text, [(cap.inner_start, cap.inner_end, X.xml_escape(caption))])
            hits += 1
            break
    print('⑤ 寫入中文名稱 %d 處' % hits)

    root = X.find_blocks(text, lambda n: n.endswith('.FormDefinition'))[0]
    text = bpm_edit.set_child(text, root, 'id', FORM_ID)
    root = X.find_blocks(text, lambda n: n.endswith('.FormDefinition'))[0]
    text = bpm_edit.set_child(text, root, 'name', X.xml_escape(FORM_NAME))
    root = X.find_blocks(text, lambda n: n.endswith('.FormDefinition'))[0]
    text = bpm_edit.set_child(text, root, 'containerOID', FORM_CONTAINER_OID)
    root = X.find_blocks(text, lambda n: n.endswith('.FormDefinition'))[0]
    text = bpm_edit.set_child(text, root, 'OID', FORM_OID)
    print('⑥ 表單 ID=%s、名稱=%s、OID 全部換新' % (FORM_ID, FORM_NAME))

    js_path = os.path.join(OUT_DIR, FORM_ID + '.js')
    if os.path.isfile(js_path):
        js = io.open(js_path, encoding='utf-8').read()
        span = X.find_blocks(text, lambda n: n == 'script')[0]
        text = X.apply_edits(text, [(span.inner_start, span.inner_end, X.xml_escape(js))])
        print('⑦ 寫入腳本 %s（%d 字元）' % (os.path.basename(js_path), len(js)))
    else:
        print('⑦ 略過腳本：%s 尚不存在' % js_path)

    text, total = bpm_edit.renumber_form_ids(text)
    print('⑧ 重編 XStream id：1…%d' % total)

    X.write_xml(out_path, text, bom)
    os.remove(tmp)
    print('   輸出 %s（%d 字元）' % (out_path, len(text)))
    return out_path


if __name__ == '__main__':
    main()
