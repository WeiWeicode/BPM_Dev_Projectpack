# -*- coding: utf-8 -*-
"""把流程邏輯從關聯表組回一張完整的流程圖。

重點：`ProcessDefinition.bpmXML` 只存畫布座標（Diagram / Node / Bounds），
流程的實際邏輯散在關聯表裡，全部以 `containerOID = ProcessDefinition.OID` 串接：

    ActivityDefinition          關卡：id / 名稱 / performType / performerIds
      └ formFieldAccessDefinitionOID → FormFieldAccessDefinition
                                        formFieldAccessControl = 該關卡的欄位權限
    TransitionDefinition        連線：from → to（conditionOID 為條件式）
    ParticipantDefinition       執行者：participantType 決定簽核對象怎麼算

關卡的 BPMN 型別（StartEvent / UserTask …）只在 bpmXML 的 Node ClassName 裡，
因此型別由 bpmXML 補齊，邏輯由關聯表提供。
"""

import re
import sys
import os

from . import config, db, extract  # noqa: E402

sys.path.insert(0, config.XML_TOOL_DIR)

from core import bpmn_handler  # noqa: E402

NODE_RE = re.compile(r'<Node\s+ClassName="([^"]+)"\s+Id="([^"]+)"')

# performerIds 可能是單一 ID，也可能以逗號或分號串接
PERFORMER_SPLIT = re.compile(r'[,;\s]+')

# core.bpmn_handler 只看結尾，但實務上 ID 多為 TEST_Button_06 這種帶流水號的命名，
# 這裡放寬成「名稱中含 button / btn 語彙」即視為按鈕。
BUTTON_TOKEN = re.compile(r'(^|_)(button|btn)(_|$)', re.I)


def _is_button(field_id):
    return bool(BUTTON_TOKEN.search(field_id or ''))


ACTIVITY_SQL = """
SELECT a.OID, a.id, a.activityDefinitionName, a.performType, a.processRole,
       a.startMode, a.finishMode, a.multiUserMode, a.bypassable, a.reassignable,
       a.formFieldAccessDefinitionOID,
       {performers} AS performerIds,
       {control} AS formFieldAccessControl
FROM ActivityDefinition a
LEFT JOIN FormFieldAccessDefinition fa ON fa.OID = a.formFieldAccessDefinitionOID
WHERE a.containerOID = ?
ORDER BY a.id
"""

TRANSITION_SQL = """
SELECT id, fromActivityDefinitionId, toActivityDefinitionId, conditionOID,
       transitionDefinitionName
FROM TransitionDefinition
WHERE containerOID = ?
ORDER BY id
"""

PARTICIPANT_SQL = """
SELECT id, participantDefinitionName, participantType, activityDefinitionId,
       organizationUnitId, employeeId, groupId, roleDefinitionName,
       titleDefinitionName, relationshipName, autoAgentId, formFieldId
FROM ParticipantDefinition
WHERE containerOID = ?
ORDER BY id
"""


def _node_types(bpm_xml):
    """從 bpmXML 取 {關卡ID: BPMN 型別}。"""
    return {node_id: class_name for class_name, node_id in NODE_RE.findall(bpm_xml or '')}


def _performers(raw, participants):
    """把 performerIds 展開成參與者定義。"""
    if not raw:
        return []
    result = []
    for token in PERFORMER_SPLIT.split(raw.strip()):
        if not token:
            continue
        participant = participants.get(token)
        result.append(participant or {'id': token, 'participantType': '(未定義)'})
    return result


def _classify(field_id, permission, lookup):
    """依表單定義的型別判斷這是按鈕還是欄位，並補上中文名。

    lookup 為該表單的 {元件ID: {'name', 'type'}}；沒有表單索引時退回 ID 命名猜測。
    """
    meta = lookup.get(field_id) if lookup else None
    item = {
        'id': field_id,
        'name': meta['name'] if meta else '',
        'type': meta['type'] if meta else '',
        'permission': permission,
        # 權限清單裡有、但表單定義中沒有 —— 代表流程版本與表單版本脫節
        'orphaned': bool(lookup) and meta is None,
    }
    is_button = (meta['type'] == 'BUTTON') if meta else _is_button(field_id)
    return item, is_button


def build(database, package_row, form_index=None):
    """組出單一流程版本的完整結構，可直接 json.dump。

    傳入 form_index（見 extract.form_index）時，按鈕與欄位以表單型別區分；
    未傳入則退回 ID 命名猜測。
    """
    container_oid = package_row.get('processDefinitionOID')
    if not container_oid:
        return {}

    bpm_xml = extract.fetch_process_xml(database, container_oid)
    node_types = _node_types(bpm_xml)

    activity_sql = ACTIVITY_SQL.format(
        performers=db.big_text('a.performerIds'),
        control=db.big_text('fa.formFieldAccessControl'))
    activity_rows = database.query(activity_sql, (container_oid,))
    transition_rows = database.query(TRANSITION_SQL, (container_oid,))
    participant_rows = database.query(PARTICIPANT_SQL, (container_oid,))

    participants = {row['id'].strip(): {k: (v.strip() if isinstance(v, str) else v)
                                        for k, v in row.items() if v not in (None, '')}
                    for row in participant_rows if row.get('id')}

    activities = []
    for row in activity_rows:
        activity_id = (row['id'] or '').strip()
        form_id, pairs = bpmn_handler._parse_access_control(
            row.get('formFieldAccessControl') or '')
        lookup = (form_index or {}).get(form_id) or {}
        buttons, fields = [], []
        for field_id, permission in pairs:
            item, is_button = _classify(field_id, permission, lookup)
            (buttons if is_button else fields).append(item)
        activities.append({
            'id': activity_id,
            'name': (row['activityDefinitionName'] or '').strip(),
            'bpmnType': node_types.get(activity_id, ''),
            'performType': (row['performType'] or '').strip(),
            'performers': _performers(row.get('performerIds'), participants),
            'formId': form_id,
            'fieldPermissions': fields,
            'buttons': buttons,
        })

    transitions = [{'id': (row['id'] or '').strip(),
                    'from': (row['fromActivityDefinitionId'] or '').strip(),
                    'to': (row['toActivityDefinitionId'] or '').strip(),
                    'hasCondition': bool((row.get('conditionOID') or '').strip())}
                   for row in transition_rows]

    return {
        'fileType': 'PROCESS',
        'processId': (package_row.get('id') or '').strip(),
        'processName': (package_row.get('processPackageName') or '').strip(),
        'version': package_row.get('version'),
        'publicationStatus': package_row.get('publicationStatus'),
        'flowType': (package_row.get('flowType') or '').strip(),
        'createdTime': package_row.get('createdTime'),
        'activities': activities,
        'transitions': transitions,
        'participants': list(participants.values()),
    }


def order_activities(graph):
    """依 transitions 由起點走訪，回傳關卡的執行順序（含分支）。"""
    activities = {a['id']: a for a in graph.get('activities', [])}
    outgoing = {}
    incoming = set()
    for transition in graph.get('transitions', []):
        outgoing.setdefault(transition['from'], []).append(transition['to'])
        incoming.add(transition['to'])
    starts = [a for a in activities if a not in incoming] or list(activities)

    ordered, seen = [], set()
    stack = list(reversed(starts))
    while stack:
        current = stack.pop()
        if current in seen or current not in activities:
            continue
        seen.add(current)
        ordered.append(activities[current])
        stack.extend(reversed(outgoing.get(current, [])))
    ordered.extend(activities[a] for a in activities if a not in seen)
    return ordered
