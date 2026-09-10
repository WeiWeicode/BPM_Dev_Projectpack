# -*- coding: utf-8 -*-
"""由 samples/快速開發測試 的教材流程，組出「AI設計的流程測試」的 .bpmn。

底稿刻意選 `已完成匯入_測試快速開發-欄位權限.bpmn` ——
那是實際匯入過 BPM 再匯出的檔案，結構經過真實系統認可。

流程結果：開單人 → 直屬主管 → 結案（刪掉底稿的通知任務與人工任務）。

刪關卡之所以要先展開 reference，是因為 XStream 的 XPATH 參照是「位置相對」的：
`../../com...ActivityDefinition/finishMode` 指的是「第一個 ActivityDefinition」，
刪掉排在前面的關卡會讓這些參照指到別人身上，甚至指到自己造成循環。

執行：python 8_BPMAIworker/tools/build_bpmn.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '1_xml_tool'))
sys.path.insert(0, HERE)

from core import xml_utils as X          # noqa: E402
from core import bpmn_handler            # noqa: E402
import xstream_ref                       # noqa: E402
import bpm_edit                          # noqa: E402

SRC = os.path.join(ROOT, 'samples', '快速開發測試', '流程',
                   '已完成匯入_測試快速開發-欄位權限.bpmn')
OUT_DIR = os.path.join(ROOT, 'samples', 'AI設計的流程測試', '流程')
OUT_NAME = 'AI設計的流程測試.bpmn'

PACKAGE_ID = 'AIDesignTestProcess'
PROCESS_NAME = 'AI設計的流程測試'
FORM_ID = 'AIDesignTestForm'
FORM_NAME = 'AI設計的流程測試'

OID_SUFFIX = 'a1de51000851cac97a977dbbf'[:24]

# 底稿裡要刪掉的關卡與其執行者
DROP_ACTIVITIES = ['ACT_SendNotify_01', 'ACT_ManualTask_05']
DROP_PARTICIPANTS = ['PAR17872072404124', 'PAR178720732832110']
DROP_TRANSITIONS = ['Link_16', 'Link_14']
# 主管關卡原本連到通知任務，改成直接結案
RETARGET = ('Link_11', 'ACT_End_04')

# 舊 ID -> (新 ID, 關卡中文名)
ACT_RENAMES = [
    ('ACT_Start_03',          'StartEvent_1',     'Event'),
    ('ACT_CreateForm_06',     'ApplyUserTask',    '開單人'),
    ('ACT_ManagerApprove_02', 'ManagerUserTask',  '直屬主管'),
    ('ACT_End_04',            'EndEvent_2',       'Event'),
]

# 各關卡的欄位／按鈕權限。沒列到的欄位＝唯讀（鼎新只存三種值，唯讀是「不列出」）
PERMISSIONS = {
    'ApplyUserTask': [
        'processInstOIDHidden', 'SerialNumber', 'SubjectTextBox', 'ContentTextArea',
        'EmpDialogInputLabel', 'DeptDoubleTextBox', 'RelatedNoDialogInput',
        'RemarkDialogInputMulti', 'UrgencyRadio', 'NotifyCheckBox', 'CategoryDropDown',
        'SiteListBox', 'NeedDate', 'NeedTime',
        'ItemGrid', 'ItemNoTextBox', 'ItemNameTextBox', 'ItemQtyTextBox',
        'Attachment', 'SubTab22', 'PasswordTextBox', 'RefLink', 'LogoImage',
        'FormBarcode', 'FormQRCode', 'SignHandWriting',
        'UploadFileButton', 'PickUserButton',
    ],
    # 主管只改備註、急件等級、簽名，其餘唯讀 —— 用來驗證關卡權限確實有差別
    'ManagerUserTask': [
        'RemarkDialogInputMulti', 'UrgencyRadio', 'SignHandWriting', 'Attachment',
    ],
}

_BPMXML_TMPL = '''<?xml version="1.0" encoding="UTF-8"?>
<Diagram x="0.0" y="0.0" width="1795.0" height="1050.0">
<Node ClassName="StartEvent" Id="StartEvent_1">
<Font name="微軟正黑體" style="0" size="15"></Font>
<Bounds x="100.0" y="100.0" width="30.0" height="30.0"></Bounds>
<ZIndex>3</ZIndex>
<Background Red="220" Green="230" Blue="242"></Background>
<Text></Text>
<TextBrush Red="0" Green="0" Blue="0"></TextBrush>
<ContainerNode NodeId="StartEvent_1">NoContainerNode</ContainerNode>
</Node>
<Node ClassName="EndEvent" Id="EndEvent_2">
<Font name="微軟正黑體" style="0" size="15"></Font>
<Bounds x="500.0" y="100.0" width="30.0" height="30.0"></Bounds>
<ZIndex>3</ZIndex>
<Background Red="220" Green="230" Blue="242"></Background>
<Text></Text>
<TextBrush Red="0" Green="0" Blue="0"></TextBrush>
<ContainerNode NodeId="EndEvent_2">NoContainerNode</ContainerNode>
</Node>
<Node ClassName="UserTask" Id="ApplyUserTask">
<Font name="微軟正黑體" style="0" size="10"></Font>
<Bounds x="190.0" y="90.0" width="80.0" height="50.0"></Bounds>
<ZIndex>3</ZIndex>
<Background Red="220" Green="230" Blue="242"></Background>
<Text>開單人</Text>
<TextBrush Red="0" Green="0" Blue="0"></TextBrush>
<ContainerNode NodeId="ApplyUserTask">NoContainerNode</ContainerNode>
</Node>
<Node ClassName="UserTask" Id="ManagerUserTask">
<Font name="微軟正黑體" style="0" size="10"></Font>
<Bounds x="330.0" y="90.0" width="80.0" height="50.0"></Bounds>
<ZIndex>3</ZIndex>
<Background Red="220" Green="230" Blue="242"></Background>
<Text>直屬主管</Text>
<TextBrush Red="0" Green="0" Blue="0"></TextBrush>
<ContainerNode NodeId="ManagerUserTask">NoContainerNode</ContainerNode>
</Node>
<Node ClassName="DiagramLink" Id="Link_5">
<Bounds x="130.0" y="115.0" width="60.0" height="0.0"></Bounds>
<ZIndex>5</ZIndex>
<Background Red="0" Green="0" Blue="0"></Background>
<Form Id="StartEvent_1">StartEvent</Form>
<To Id="ApplyUserTask">UserTask</To>
<Text></Text>
<LinkShape>2</LinkShape>
<PointList>
<Point x="130" y="115"></Point>
<Point x="190" y="115"></Point>
</PointList>
<ContainerNode NodeId="NoNodeId">NoContainerNode</ContainerNode>
</Node>
<Node ClassName="DiagramLink" Id="Link_6">
<Bounds x="270.0" y="115.0" width="60.0" height="0.0"></Bounds>
<ZIndex>5</ZIndex>
<Background Red="0" Green="0" Blue="0"></Background>
<Form Id="ApplyUserTask">UserTask</Form>
<To Id="ManagerUserTask">UserTask</To>
<Text></Text>
<LinkShape>2</LinkShape>
<PointList>
<Point x="270" y="115"></Point>
<Point x="330" y="115"></Point>
</PointList>
<ContainerNode NodeId="NoNodeId">NoContainerNode</ContainerNode>
</Node>
<Node ClassName="DiagramLink" Id="Link_11">
<Bounds x="410.0" y="115.0" width="90.0" height="0.0"></Bounds>
<ZIndex>5</ZIndex>
<Background Red="0" Green="0" Blue="0"></Background>
<Form Id="ManagerUserTask">UserTask</Form>
<To Id="EndEvent_2">EndEvent</To>
<Text></Text>
<LinkShape>2</LinkShape>
<PointList>
<Point x="410" y="115"></Point>
<Point x="500" y="115"></Point>
</PointList>
<ContainerNode NodeId="NoNodeId">NoContainerNode</ContainerNode>
</Node>
</Diagram>'''

RISKY = ('ActivityDefinition', 'ParticipantDefinition', 'RelevantDataDefinition',
         'TransitionDefinition', 'DecisionCondition', 'ActivitySetDefinition')


def main():
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    out_path = os.path.join(OUT_DIR, OUT_NAME)
    tmp = out_path + '.tmp'

    text, bom = X.read_xml(SRC)
    print('① 讀入樣板 %s（%d 字元）' % (os.path.basename(SRC), len(text)))

    text, n, skipped = xstream_ref.inline_refs(text, lambda p: any(k in p for k in RISKY))
    print('② 展開位置相關的 reference %d 處（略過 %d）' % (n, len(skipped)))
    for s in skipped:
        print('   略過:', s)

    ns = 'com.dsc.nana.domain.workflow__definition.'
    text = bpm_edit.drop_all(text, ns + 'ActivityDefinition', DROP_ACTIVITIES)
    text = bpm_edit.drop_all(text, ns + 'ParticipantDefinition', DROP_PARTICIPANTS)
    text = bpm_edit.drop_all(text, ns + 'TransitionDefinition', DROP_TRANSITIONS)
    print('③ 刪除 %d 個關卡、%d 個執行者、%d 條連線'
          % (len(DROP_ACTIVITIES), len(DROP_PARTICIPANTS), len(DROP_TRANSITIONS)))

    link = bpm_edit.find_by_child_id(text, ns + 'TransitionDefinition', RETARGET[0])
    if link is None:
        raise ValueError('找不到要改接的連線 %s' % RETARGET[0])
    text = bpm_edit.set_child(text, link, 'toActivityDefinitionId', RETARGET[1])
    print('④ %s 改接到 %s' % RETARGET)

    X.write_xml(tmp, text, bom)
    cfg = {'activities': [{'originalId': o, 'id': n2, 'name': t,
                           'buttons': [], 'fieldPermissions': []}
                          for o, n2, t in ACT_RENAMES]}
    acts, _fields, msgs = bpmn_handler.write_back(tmp, cfg, tmp)
    print('⑤ 改名 %d 個關卡' % acts)
    for m in msgs:
        print('   ' + m)

    text, _ = X.read_xml(tmp)
    for _old, new, name in ACT_RENAMES:
        s = bpm_edit.find_by_child_id(text, ns + 'ActivityDefinition', new)
        text = bpm_edit.set_child(text, s, 'name', X.xml_escape(name))
    print('⑥ 寫入關卡中文名稱')

    for act_id, fields in PERMISSIONS.items():
        text = bpm_edit.set_field_permissions(text, act_id, FORM_ID, fields)
    print('⑦ 寫入欄位權限：%s' % '、'.join(
        '%s %d 項' % (k, len(v)) for k, v in PERMISSIONS.items()))

    # 表單繫結
    rd = bpm_edit.find_by_child_id(text, ns + 'RelevantDataDefinition', 'quickDevTestFormImport')
    if rd is None:
        raise ValueError('找不到繫結表單的 RelevantDataDefinition')
    text = bpm_edit.set_child(text, rd, 'id', FORM_ID)
    rd = bpm_edit.find_by_child_id(text, ns + 'RelevantDataDefinition', FORM_ID)
    text = bpm_edit.set_child(text, rd, 'name', X.xml_escape(FORM_NAME))
    # 關卡的 WebApplication 是靠 <relevantDataDefinitionId> 找到表單的，
    # 只改 RelevantDataDefinition 的 <id> 而漏掉這裡，關卡就會開不出表單
    n_bind = 0
    for tag in ('formDefinitionId', 'relevantDataDefinitionId'):
        pat = re.compile(r'<%s>([^<]*)</%s>' % (tag, tag))
        pieces, last = [], 0
        for m in pat.finditer(text):
            if m.group(1) in ('quickDevTestFormImport', 'quickDevTestForm'):
                pieces.append(text[last:m.start(1)])
                pieces.append(FORM_ID)
                last = m.end(1)
                n_bind += 1
        pieces.append(text[last:])
        text = ''.join(pieces)
    print('⑧ 繫結表單 %s（%s）：更新 %d 處參照' % (FORM_ID, FORM_NAME, n_bind))

    # 流程包與流程定義的 ID / 名稱
    pkg = X.find_blocks(text, lambda n: n == ns + 'ProcessPackage')[0]
    text = bpm_edit.set_child(text, pkg, 'id', PACKAGE_ID)
    pkg = X.find_blocks(text, lambda n: n == ns + 'ProcessPackage')[0]
    text = bpm_edit.set_child(text, pkg, 'name', X.xml_escape(PROCESS_NAME))
    pkg = X.find_blocks(text, lambda n: n == ns + 'ProcessPackage')[0]
    text = bpm_edit.set_child(text, pkg, 'mainProcessDefinitionId', PACKAGE_ID)
    pd = X.find_blocks(text, lambda n: n == ns + 'ProcessDefinition')[0]
    text = bpm_edit.set_child(text, pd, 'id', PACKAGE_ID)
    pd = X.find_blocks(text, lambda n: n == ns + 'ProcessDefinition')[0]
    text = bpm_edit.set_child(text, pd, 'name', X.xml_escape(PROCESS_NAME))
    print('⑨ 流程 ID=%s、名稱=%s' % (PACKAGE_ID, PROCESS_NAME))

    span = X.find_blocks(text, lambda n: n == 'bpmXML')[0]
    text = X.apply_edits(text, [(span.inner_start, span.inner_end,
                                 X.xml_escape(_BPMXML_TMPL))])
    print('⑩ 重畫流程圖（4 節點 / 3 連線）')

    text, n_oid = bpm_edit.remap_oids(text, 0x7a10d000, OID_SUFFIX)
    print('⑪ 換掉 %d 個 OID' % n_oid)

    X.write_xml(out_path, text, bom)
    os.remove(tmp)
    print('   輸出 %s（%d 字元）' % (out_path, len(text)))
    return out_path


if __name__ == '__main__':
    main()
