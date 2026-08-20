# -*- coding: utf-8 -*-
"""流程 (.bpmn) 萃取與回寫模組。

萃取：關卡名稱 / 關卡 ID / 節點類型，以及 <formFieldAccessControl> 內
      逃脫 XML 所描述的按鈕與欄位權限矩陣。
回寫：以 originalId 為主鍵定位關卡，連動更新
      1. <ActivityDefinition><id>
      2. <bpmXML> 內的 Node Id / ContainerNode NodeId / DiagramLink 的 Form/To Id
      3. <activityDefinitionId> / <fromActivityDefinitionId> / <toActivityDefinitionId>
      欄位與按鈕改名則同步更新 formFieldAccessControl 內的標籤名，
      以及郵件樣板中的 <#表單ID~~欄位ID> 參照。
"""

import re

from . import xml_utils as X

WF_NS = 'com.dsc.nana.domain.workflow__definition.'
ACTIVITY_CLASS = WF_NS + 'ActivityDefinition'
PROCESS_CLASS = WF_NS + 'ProcessDefinition'
PACKAGE_CLASS = WF_NS + 'ProcessPackage'

ID_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# 只比對「葉節點且內容剛好等於舊 ID」的參照標籤，避免誤傷
_LEAF_RE = re.compile(r'<([A-Za-z_][A-Za-z0-9_.\-:]*)>([^<>]*)</\1>')
_REF_TAG_RE = re.compile(r'(activitydefinitionid|activityid)$')

BUTTON_SUFFIXES = ('button', 'btn')


def _is_button(field_id):
    low = field_id.lower()
    return low.endswith(BUTTON_SUFFIXES)


def _parse_access_control(raw):
    """解析逃脫後的 <FormFieldAccessControl>，回傳 (formId, [(欄位ID, 權限), ...])。"""
    if not raw.strip():
        return '', []
    inner = X.xml_unescape(raw)
    m = re.search(r'<FormFieldAccessControl>\s*<([A-Za-z_][\w.\-]*)>(.*?)</\1>',
                  inner, re.S)
    if not m:
        return '', []
    form_id = m.group(1)
    pairs = re.findall(r'<([A-Za-z_][\w.\-]*)>([^<>]*)</\1>', m.group(2))
    return form_id, pairs


class Activity(object):
    def __init__(self, text, span):
        self.span = span
        kids = X.direct_children(text, span)
        self.kids = kids
        self.id_span = X.child(text, span, 'id', kids)
        self.id = text[self.id_span.inner_start:self.id_span.inner_end] if self.id_span else ''
        self.name = X.xml_unescape(X.child_text(text, span, 'name', kids))
        self.bpmn_type = X.child_text(text, span, 'bpmnType', kids)
        # formFieldAccessControl 位於 <formFieldAccessDefinition> 之下，非直屬子節點
        fac = X.find_blocks(text, lambda n: n == 'formFieldAccessControl',
                            span.inner_start, span.inner_end)
        self.fac_span = fac[0] if fac else None
        raw = text[self.fac_span.inner_start:self.fac_span.inner_end] if self.fac_span else ''
        self.form_id, self.permissions = _parse_access_control(raw)


def _activities(text):
    return [Activity(text, s)
            for s in X.find_blocks(text, lambda n: n == ACTIVITY_CLASS)]


def _meta(text):
    package_id = process_id = process_name = ''
    pkgs = X.find_blocks(text, lambda n: n == PACKAGE_CLASS)
    if pkgs:
        kids = X.direct_children(text, pkgs[0])
        package_id = X.child_text(text, pkgs[0], 'id', kids)
        process_name = X.xml_unescape(X.child_text(text, pkgs[0], 'name', kids))
    procs = X.find_blocks(text, lambda n: n == PROCESS_CLASS)
    if procs:
        kids = X.direct_children(text, procs[0])
        process_id = X.child_text(text, procs[0], 'id', kids)
        pname = X.xml_unescape(X.child_text(text, procs[0], 'name', kids))
        if pname:
            process_name = pname
    return package_id, process_id, process_name


def extract(path):
    """.bpmn -> dict（可直接 json.dump）。"""
    text, _bom = X.read_xml(path)
    package_id, process_id, process_name = _meta(text)

    activities = []
    for a in _activities(text):
        buttons = []
        fields = []
        for fid, perm in a.permissions:
            item = {'originalId': fid, 'id': fid, 'permission': perm}
            (buttons if _is_button(fid) else fields).append(item)
        entry = {
            'name': a.name,
            'originalId': a.id,
            'id': a.id,
            'type': a.bpmn_type,
            'buttons': buttons,
            'fieldPermissions': fields,
        }
        if a.form_id:
            entry['formId'] = a.form_id
        activities.append(entry)

    return {
        'fileType': 'BPMN',
        'packageId': package_id,
        'processId': process_id,
        'processName': process_name,
        'sourceFile': path.replace('\\', '/').split('/')[-1],
        'activities': activities,
    }


def write_back(xml_path, config, out_path):
    """依 config 回寫成 out_path，回傳 (更新關卡數, 更新欄位數, 提醒訊息清單)。"""
    text, bom = X.read_xml(xml_path)
    acts = _activities(text)
    by_original = {}
    for a in acts:
        if a.id:
            by_original.setdefault(a.id, a)

    entries = config.get('activities') or []
    messages = []
    act_renames = []
    seen_new = {}

    for e in entries:
        old = (e.get('originalId') or '').strip()
        new = (e.get('id') or '').strip()
        title = e.get('name') or old
        if not old:
            raise ValueError('JSON 中有關卡缺少 originalId，無法定位（name=%s）' % title)
        if old not in by_original:
            raise ValueError('原始檔中找不到關卡 originalId：%s（名稱：%s）' % (old, title))
        if not new:
            raise ValueError('關卡「%s」的 id 不可為空' % title)
        if old == new:
            continue
        if not ID_PATTERN.match(new):
            raise ValueError('新關卡 ID「%s」格式不合法：僅允許英數字與底線，且不可數字開頭' % new)
        if new in seen_new:
            raise ValueError('JSON 內新關卡 ID 重複：%s' % new)
        seen_new[new] = old
        act_renames.append((old, new, title))

    rename_map = dict((o, n) for o, n, _ in act_renames)
    final_ids = {}
    for a in acts:
        target = rename_map.get(a.id, a.id)
        if target in final_ids:
            raise ValueError('關卡 ID 衝突：關卡「%s」與「%s」改名後都會變成「%s」'
                             % (final_ids[target], a.id, target))
        final_ids[target] = a.id

    edits = []

    # 1. 關卡本身的 <id>，以及關卡內部與其同值的 <id>
    #    （StartEvent / EndEvent 的 <activityType> 會再複製一份同樣的 id）
    for old, new, _title in act_renames:
        a = by_original[old]
        seen_pos = set()
        for m in _LEAF_RE.finditer(text, a.span.inner_start, a.span.inner_end):
            if m.group(1) != 'id' or m.group(2) != old:
                continue
            if m.start(2) in seen_pos:
                continue
            seen_pos.add(m.start(2))
            edits.append((m.start(2), m.start(2) + len(old), new))
        if a.id_span is not None and a.id_span.inner_start not in seen_pos:
            edits.append((a.id_span.inner_start, a.id_span.inner_end, new))

    # 2. 參照標籤（activityDefinitionId / fromActivityDefinitionId / toActivityDefinitionId）
    ref_hits = 0
    if rename_map:
        for m in _LEAF_RE.finditer(text):
            tag, value = m.group(1), m.group(2)
            if value not in rename_map:
                continue
            if not _REF_TAG_RE.search(tag.lower()):
                continue
            start = m.start(2)
            edits.append((start, start + len(value), rename_map[value]))
            ref_hits += 1

    # 3. <bpmXML> 內的圖形節點與連線（逃脫過的 Id=&quot;...&quot;）
    diagram_hits = 0
    if rename_map:
        for span in X.find_blocks(text, lambda n: n == 'bpmXML'):
            body = text[span.inner_start:span.inner_end]
            for old, new in rename_map.items():
                needle = 'Id=&quot;%s&quot;' % old
                repl = 'Id=&quot;%s&quot;' % new
                pos = 0
                while True:
                    i = body.find(needle, pos)
                    if i < 0:
                        break
                    abs_start = span.inner_start + i
                    edits.append((abs_start, abs_start + len(needle), repl))
                    diagram_hits += 1
                    pos = i + len(needle)

    # 4. 欄位 / 按鈕改名 → formFieldAccessControl 與郵件樣板
    field_renames = {}     # (formId, oldId) -> newId
    field_count = 0
    for e in entries:
        act = by_original.get((e.get('originalId') or '').strip())
        if act is None or act.fac_span is None:
            continue
        present = dict(act.permissions)
        local = {}
        for item in (e.get('buttons') or []) + (e.get('fieldPermissions') or []):
            old = (item.get('originalId') or '').strip()
            new = (item.get('id') or '').strip()
            if not old or not new or old == new:
                continue
            if old not in present:
                raise ValueError('關卡「%s」的權限設定中找不到欄位 %s' % (act.name, old))
            if not ID_PATTERN.match(new):
                raise ValueError('新欄位 ID「%s」格式不合法' % new)
            local[old] = new
            key = (act.form_id, old)
            if key in field_renames and field_renames[key] != new:
                raise ValueError('欄位「%s」在不同關卡被改成不同的新 ID（%s / %s）'
                                 % (old, field_renames[key], new))
            field_renames[key] = new

        body = text[act.fac_span.inner_start:act.fac_span.inner_end]
        for old, new in local.items():
            for pattern, repl in (('&lt;%s&gt;' % old, '&lt;%s&gt;' % new),
                                  ('&lt;/%s&gt;' % old, '&lt;/%s&gt;' % new)):
                pos = 0
                while True:
                    i = body.find(pattern, pos)
                    if i < 0:
                        break
                    abs_start = act.fac_span.inner_start + i
                    edits.append((abs_start, abs_start + len(pattern), repl))
                    pos = i + len(pattern)
            field_count += 1

    # 欄位在某關卡改名、卻在其他關卡維持舊名 → 提醒
    for (form_id, old), new in field_renames.items():
        stale = [a.name for a in acts
                 if a.form_id == form_id and old in dict(a.permissions)
                 and not _renamed_here(entries, a.id, old)]
        if stale:
            messages.append('! 欄位「%s」在關卡 %s 未同步改名，請確認是否刻意保留'
                            % (old, '、'.join(stale)))

    # 郵件樣板 <#表單ID~~欄位ID>
    mail_hits = 0
    for (form_id, old), new in field_renames.items():
        needle = '&lt;#%s~~%s&gt;' % (form_id, old)
        repl = '&lt;#%s~~%s&gt;' % (form_id, new)
        pos = 0
        while True:
            i = text.find(needle, pos)
            if i < 0:
                break
            edits.append((i, i + len(needle), repl))
            mail_hits += 1
            pos = i + len(needle)
    if mail_hits:
        messages.append('  郵件樣板中同步更新了 %d 處 <#表單~~欄位> 參照' % mail_hits)

    if act_renames:
        messages.append('  流程圖節點/連線更新 %d 處、關卡參照更新 %d 處'
                        % (diagram_hits, ref_hits))

    if not edits:
        return 0, 0, messages

    X.write_xml(out_path, X.apply_edits(text, edits), bom)
    return len(act_renames), field_count, messages


def _renamed_here(entries, activity_id, field_old_id):
    for e in entries:
        if (e.get('originalId') or '') != activity_id:
            continue
        for item in (e.get('buttons') or []) + (e.get('fieldPermissions') or []):
            if (item.get('originalId') or '') == field_old_id:
                return (item.get('id') or '') != field_old_id
    return False
