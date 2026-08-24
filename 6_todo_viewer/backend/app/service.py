# -*- coding: utf-8 -*-
"""查詢邏輯。

唯讀。所有查詢一律參數化，絕不字串拼接使用者輸入（IN 子句的 ? 佔位符由
筆數決定，值仍走參數）。查詢路徑的依據見 docs/待辦狀態語意.md：

- 待簽核在 LocalToDoWorkItem，**不在** WorkItem.performerOID
  （後者只在關卡完成時才寫入，未完成的關卡該欄是 NULL）
- 待辦只取 WorkItem.currentState 0 與 1；97 是卡住的異常關卡，另計不混入
"""

import os
import xml.etree.ElementTree as ET

from . import settings          # 先載入，它會把 3_db_explorer 加進 sys.path

from bpm_kb import config, extract   # noqa: E402
from bpm_kb.db import Database       # noqa: E402
from core import form_handler        # noqa: E402  bpm_kb 已把 1_xml_tool 加進 sys.path

# ProcessInstance.currentState 對照。與 BPMGeneralController.js 的
# convertProcessStateToChinese 一致；191 實測只出現 1 / 3 / 4 / 5
PROCESS_STATES = {
    0: '未開始',
    1: '進行中',
    2: '已暫停',
    3: '已結案',
    4: '已撤銷',
    5: '已中止',
}

# 待辦的工作項目狀態；97 不在此列，視為異常另計
TODO_STATES = (0, 1)
ABNORMAL_STATE = 97


def process_state_label(code):
    if code is None:
        return ''
    return PROCESS_STATES.get(code, '其他(%s)' % code)


# ---------------------------------------------------------------- 連線

def db_settings(host=None):
    """把 .env 的設定套上指定主機的位址與（選填的）專屬帳密。"""
    entry = settings.host_entry(host or settings.DEFAULT_HOST)
    values = dict(config.load())
    values['BPM_DB_HOST'] = entry[2]
    # 正式區帳密通常與測試區不同，用 BPM_DB_USER_190 / BPM_DB_PASSWORD_190 覆寫
    for field in ('BPM_DB_USER', 'BPM_DB_PASSWORD', 'BPM_DB_NAME'):
        override = os.environ.get('%s_%s' % (field, entry[0]))
        if override:
            values[field] = override
    return values


def connect(host=None):
    return Database(db_settings(host))


def host_list():
    return [{'key': e[0], 'label': e[1], 'address': e[2],
             'production': e[3], 'web_base': e[4]} for e in settings.HOSTS]


def health(host=None):
    entry = settings.host_entry(host or settings.DEFAULT_HOST)
    values = db_settings(entry[0])
    result = {'ok': False, 'host': entry[0], 'host_label': entry[1],
              'production': entry[3], 'hosts': host_list(),
              'connection': config.describe(values), 'database': values.get('BPM_DB_NAME', '')}
    try:
        with Database(values) as database:
            database.scalar('SELECT 1')
        result['ok'] = True
    except Exception as exc:
        result['error'] = str(exc)
    return result


# ---------------------------------------------------------------- 深連結

def perform_url(host, user_id, work_item_oid):
    """組出等同通知信裡那條連結的網址。

    只是產生一條給人點的連結，程式本身不對該主機發出任何請求。
    缺任一材料就回空字串 —— 寧可讓畫面顯示「無可用連結」，也不給半條假網址。
    """
    entry = settings.host_entry(host or settings.DEFAULT_HOST)
    base = (entry[4] or '').rstrip('/')
    if not base or not user_id or not work_item_oid:
        return ''
    return ('%s/NaNaWeb/GP/PerformWorkFromMail'
            '?hdnMethod=performWorkFromMail&hdnUserId=%s&hdnWorkItemOID=%s'
            % (base, user_id, work_item_oid))


def trace_url(host, user_id, process_instance_oid):
    """流程追蹤（唯讀檢視）的網址。

    來源不是猜的：BPM 自己寄的通知信正文（`Mails.message`、
    `ProcessNotification.message`）裡就有這條格式。
    `hdnProcessInstOID` 是 **ProcessInstance.OID**，不是 contextOID ——
    取樣 60 筆信件內的 OID，60 筆全部對到 OID、0 筆對到 contextOID。

    這條不需要工作項目，所以已結案、我申請的、別人待簽的單都能連。
    """
    entry = settings.host_entry(host or settings.DEFAULT_HOST)
    base = (entry[4] or '').rstrip('/')
    if not base or not user_id or not process_instance_oid:
        return ''
    return ('%s/NaNaWeb/GP/WMS/TraceProcess/TraceProcessMain'
            '?hdnMethod=traceProcessFromMail&hdnCurrentUserId=%s&hdnProcessInstOID=%s'
            % (base, user_id, process_instance_oid))


# ---------------------------------------------------------------- 使用者

def _user_row(row):
    return {'oid': (row['OID'] or '').strip(),
            'id': (row['id'] or '').strip(),
            'user_name': row['userName'] or '',
            'mail_address': row['mailAddress'] or '',
            'left': row['leaveDate'] is not None}


def search_users(keyword, host=None, limit=50):
    """id 精確、姓名模糊。一律回候選清單 —— 同一個人可能有多個公司別帳號。"""
    keyword = (keyword or '').strip()
    if not keyword:
        return []
    sql = ('SELECT TOP (?) OID, id, userName, mailAddress, leaveDate FROM Users '
           'WHERE id = ? OR userName LIKE ? OR mailAddress LIKE ? '
           'ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END, id')
    like = '%' + keyword + '%'
    with connect(host) as database:
        rows = database.query(sql, (limit, keyword, like, like, keyword))
    return [_user_row(r) for r in rows]


def get_user(user_id, host=None):
    """以 Users.id 取單一使用者。找不到回 None，由端點轉成 404。"""
    with connect(host) as database:
        rows = database.query(
            'SELECT TOP 1 OID, id, userName, mailAddress, leaveDate FROM Users WHERE id = ?',
            ((user_id or '').strip(),))
    return _user_row(rows[0]) if rows else None


# ---------------------------------------------------------------- 待簽核

_TODO_SQL = '''
SELECT T.workItemOID, T.subject, T.processInstanceName, T.createdTime,
       W.workItemName, W.currentState AS workItemState,
       PI.serialNumber, PI.currentState AS processState, PI.OID AS processOID
FROM LocalToDoWorkItem T
JOIN WorkItem W ON T.workItemOID = W.OID
LEFT JOIN ProcessInstance PI ON W.contextOID = PI.contextOID
WHERE T.userOID = ?
ORDER BY T.createdTime DESC
'''


def list_todo(user, host=None):
    """待簽核清單。

    回傳同時帶 abnormal_total：currentState = 97 的關卡卡在流程裡但 BPM 不計入
    待辦數，排除它們是對的，但要說出排除了幾筆。
    """
    with connect(host) as database:
        rows = database.query(_TODO_SQL, (user['oid'],))

    items = []
    abnormal = 0
    for row in rows:
        state = row['workItemState']
        if state not in TODO_STATES and state != ABNORMAL_STATE:
            continue
        if state == ABNORMAL_STATE:
            abnormal += 1
        oid = (row['workItemOID'] or '').strip()
        items.append({
            'work_item_oid': oid,
            'work_item_name': row['workItemName'] or '',
            'work_item_state': state,
            'abnormal': state == ABNORMAL_STATE,
            'serial_number': row['serialNumber'] or '',
            'process_instance_name': row['processInstanceName'] or '',
            'subject': row['subject'] or '',
            'created_time': row['createdTime'],
            'process_state': row['processState'],
            'process_state_label': process_state_label(row['processState']),
            'perform_url': perform_url(host, user['id'], oid),
            'trace_url': trace_url(host, user['id'], (row['processOID'] or '').strip()),
        })
    return {'user': user, 'host': host or settings.DEFAULT_HOST,
            'total': len(items) - abnormal, 'abnormal_total': abnormal,
            'items': items}


# ---------------------------------------------------------------- 我申請的

def list_requested(user, host=None, state=None, offset=0, limit=None):
    limit = _clamp(limit)
    where = 'PI.requesterOID = ?'
    params = [user['oid']]
    if state is not None:
        where += ' AND PI.currentState = ?'
        params.append(state)

    count_sql = 'SELECT COUNT(*) FROM ProcessInstance PI WHERE ' + where
    page_sql = ('SELECT PI.serialNumber, PI.processInstanceName, PI.contextOID, PI.OID, '
                'CAST(PI.subject AS nvarchar(max)) AS subject, '
                'PI.createdTime, PI.currentState AS processState '
                'FROM ProcessInstance PI WHERE ' + where +
                ' ORDER BY PI.createdTime DESC '
                'OFFSET ? ROWS FETCH NEXT ? ROWS ONLY')

    with connect(host) as database:
        total = database.scalar(count_sql, tuple(params)) or 0
        rows = database.query(page_sql, tuple(params + [offset, limit]))
        activities = _open_activities(database, [r['contextOID'] for r in rows])

    items = [{
        'serial_number': r['serialNumber'] or '',
        'process_instance_name': r['processInstanceName'] or '',
        'subject': r['subject'] or '',
        'created_time': r['createdTime'],
        'process_state': r['processState'],
        'process_state_label': process_state_label(r['processState']),
        'current_activities': activities.get((r['contextOID'] or '').strip(), []),
        'trace_url': trace_url(host, user['id'], (r['OID'] or '').strip()),
    } for r in rows]
    return {'user': user, 'host': host or settings.DEFAULT_HOST, 'total': total,
            'offset': offset, 'limit': limit, 'items': items}


def _open_activities(database, context_oids):
    """一次撈完本頁所有單子目前未完成的關卡名稱，避免 N+1 查詢。"""
    oids = [(o or '').strip() for o in context_oids if o]
    if not oids:
        return {}
    marks = ','.join('?' * len(oids))
    states = ','.join('?' * len(TODO_STATES))
    sql = ('SELECT contextOID, workItemName FROM WorkItem '
           'WHERE contextOID IN (%s) AND currentState IN (%s)' % (marks, states))
    result = {}
    for row in database.query(sql, tuple(oids) + TODO_STATES):
        key = (row['contextOID'] or '').strip()
        name = row['workItemName'] or ''
        names = result.setdefault(key, [])
        if name and name not in names:
            names.append(name)
    return result


# ---------------------------------------------------------------- 我經辦過的

def list_handled(user, host=None, offset=0, limit=None):
    limit = _clamp(limit)
    count_sql = ('SELECT COUNT(*) FROM WorkItem W '
                 'WHERE W.performerOID = ? AND W.currentState = 3')
    page_sql = ('SELECT W.OID, W.workItemName, W.completedTime, '
                'CAST(W.executiveComment AS nvarchar(max)) AS executiveComment, '
                'PI.serialNumber, PI.processInstanceName, '
                'CAST(PI.subject AS nvarchar(max)) AS subject, '
                'PI.currentState AS processState, PI.OID AS processOID '
                'FROM WorkItem W '
                'LEFT JOIN ProcessInstance PI ON W.contextOID = PI.contextOID '
                'WHERE W.performerOID = ? AND W.currentState = 3 '
                'ORDER BY W.completedTime DESC '
                'OFFSET ? ROWS FETCH NEXT ? ROWS ONLY')
    with connect(host) as database:
        total = database.scalar(count_sql, (user['oid'],)) or 0
        rows = database.query(page_sql, (user['oid'], offset, limit))

    items = [{
        'work_item_oid': (r['OID'] or '').strip(),
        'work_item_name': r['workItemName'] or '',
        'serial_number': r['serialNumber'] or '',
        'process_instance_name': r['processInstanceName'] or '',
        'subject': r['subject'] or '',
        'completed_time': r['completedTime'],
        'executive_comment': r['executiveComment'] or '',
        'process_state': r['processState'],
        'process_state_label': process_state_label(r['processState']),
        'trace_url': trace_url(host, user['id'], (r['processOID'] or '').strip()),
    } for r in rows]
    return {'user': user, 'host': host or settings.DEFAULT_HOST, 'total': total,
            'offset': offset, 'limit': limit, 'items': items}


def _clamp(limit):
    if not limit:
        return settings.DEFAULT_LIMIT
    return max(1, min(int(limit), settings.MAX_LIMIT))


# ---------------------------------------------------------------- 單筆詳情

_INSTANCE_SQL = '''
SELECT TOP 1
       PI.serialNumber AS piSerial, PI.contextOID, PI.OID AS processOID,
       PI.processInstanceName,
       PI.currentState AS processState, PI.createdTime,
       CAST(PI.subject AS nvarchar(max)) AS subject,
       U.id AS requesterId, U.userName AS requesterName
FROM ProcessInstance PI
LEFT JOIN Users U ON U.OID = PI.requesterOID
WHERE PI.serialNumber = ?
'''

# 表單必須另外查，不能併進上面的查詢。
# LocalRelevantData 一張單有多列：表單一列，其餘是 processSerialNumber、
# isSeparateByVerNo 這類流程變數。併著查又 SELECT TOP 1 會隨機撞到變數列，
# FormInstance 就接成 NULL —— 191 實測 836 張進行中的單會有 383 張抓不到表單。
# 這裡用 JOIN（而非 LEFT JOIN）把非表單的列篩掉。
_FORM_SQL = '''
SELECT TOP 1 FI.serialNumber AS fiSerial, FI.definitionOID,
       CAST(FI.fieldValues AS nvarchar(max)) AS fieldValues,
       FD.id AS formId, FD.formDefinitionName AS formName
FROM LocalRelevantData LRD
JOIN FormInstance FI ON FI.OID = LRD.valueOID
LEFT JOIN FormDefinition FD ON FD.OID = FI.definitionOID
WHERE LRD.containerOID = ?
'''

_HISTORY_SQL = '''
SELECT W.workItemName, W.createdTime, W.completedTime, W.currentState,
       CAST(W.executiveComment AS nvarchar(max)) AS executiveComment,
       U.id AS performerId, U.userName AS performerName
FROM WorkItem W
LEFT JOIN Users U ON U.OID = W.performerOID
WHERE W.contextOID = ?
ORDER BY W.createdTime ASC
'''


# 表單定義的欄位對照快取：{(host, definitionOID): {元件ID: {'name', 'type', 'order'}}}
# 一份定義的 XML 動輒 1MB、解析約 90ms，但同一版定義的內容不會變，
# 所以以 definitionOID 為 key 快取。要清掉就重啟服務。
_LABEL_CACHE = {}


def field_labels(database, definition_oid, host=None):
    """取這張單所用表單定義的「元件ID → 中文顯示名」。

    用 FormInstance.definitionOID 精準對到**這張單當時用的那一版**定義，
    不是表單的最新版 —— 版本落差會讓欄位名對不上。
    解析沿用 bpm_kb.extract 與 core.form_handler，不另寫一套（見 AGENTS.md 7.5）。
    """
    definition_oid = (definition_oid or '').strip()
    if not definition_oid:
        return {}
    key = (host or settings.DEFAULT_HOST, definition_oid)
    if key not in _LABEL_CACHE:
        xml = extract.fetch_form_xml(database, definition_oid)
        if not xml:
            return {}
        summary = form_handler.extract_text(xml, definition_oid)
        _LABEL_CACHE[key] = {
            field['id']: {'name': field['name'], 'type': field['type'], 'order': index}
            for index, field in enumerate(summary.get('fields', [])) if field.get('id')
        }
    return _LABEL_CACHE[key]


def get_instance(serial_number, host=None, user_id=''):
    """單筆詳情。找不到回 None。

    user_id 只用來組追蹤網址（`hdnCurrentUserId`）；不給就不出連結。
    """
    labels = {}
    label_error = ''
    with connect(host) as database:
        rows = database.query(_INSTANCE_SQL, ((serial_number or '').strip(),))
        if not rows:
            return None
        row = rows[0]
        history = database.query(_HISTORY_SQL, (row['contextOID'],))
        forms = database.query(_FORM_SQL, (row['contextOID'],))
        if forms and forms[0]['definitionOID']:
            try:
                labels = field_labels(database, forms[0]['definitionOID'], host)
            except Exception as exc:
                # 取不到中文名不該讓整張單看不到 —— 欄位值照顯示，但要說出原因
                label_error = '表單定義解析失敗，僅顯示欄位 ID：%s' % exc

    form = forms[0] if forms else {'fiSerial': '', 'fieldValues': None,
                                   'formId': '', 'formName': ''}
    detail = {
        'pi_serial_number': row['piSerial'] or '',
        'fi_serial_number': form['fiSerial'] or '',
        'process_instance_name': row['processInstanceName'] or '',
        'subject': row['subject'] or '',
        'requester_id': (row['requesterId'] or '').strip(),
        'requester_name': row['requesterName'] or '',
        'created_time': row['createdTime'],
        'process_state': row['processState'],
        'process_state_label': process_state_label(row['processState']),
        'form_id': (form['formId'] or '').strip(),
        'form_name': form['formName'] or '',
        'trace_url': trace_url(host, user_id, (row['processOID'] or '').strip()),
        'field_values': [],
        'grid_values': [],
        'attachments': [],
        'approval_history': [{
            'work_item_name': h['workItemName'] or '',
            'performer_id': (h['performerId'] or '').strip(),
            'performer_name': h['performerName'] or '',
            'created_time': h['createdTime'],
            'completed_time': h['completedTime'],
            'executive_comment': h['executiveComment'] or '',
            'work_item_state': h['currentState'],
        } for h in history],
        'form_parse_error': '',
        'label_source_error': label_error,
    }

    if form['fieldValues']:
        try:
            fields, grids, attachments = parse_field_values(form['fieldValues'])
            detail['field_values'] = _label_fields(fields, labels)
            detail['grid_values'] = _label_grids(grids, labels)
            detail['attachments'] = attachments
        except ET.ParseError as exc:
            # 解析失敗要說出來，不能回空表單假裝這張單沒欄位
            detail['form_parse_error'] = 'fieldValues XML 解析失敗：%s' % exc
    return detail


def _label_fields(fields, labels):
    """把欄位值配上中文名，並依表單版面順序排列。

    定義裡查不到的欄位（隱藏變數、版本落差）排在最後、name 留空，
    前端顯示 ID —— 不猜名稱、也不丟掉這些值。
    """
    unknown_order = len(labels)
    result = [{
        'id': field_id,
        'name': labels.get(field_id, {}).get('name', ''),
        'type': labels.get(field_id, {}).get('type', ''),
        'value': value,
    } for field_id, value in fields.items()]
    result.sort(key=lambda item: labels.get(item['id'], {}).get('order', unknown_order))
    return result


def _label_grids(grids, labels):
    """Grid 本身有中文名（型別 LIST）；欄位（列內 item）的中文名不在表單定義裡，
    直接顯示 item 的 ID。"""
    blocks = []
    for grid_id, rows in grids.items():
        columns = list(rows[0].keys()) if rows else []
        blocks.append({
            'id': grid_id,
            'name': labels.get(grid_id, {}).get('name', ''),
            'columns': columns,
            'rows': rows,
        })
    blocks.sort(key=lambda block: labels.get(block['id'], {}).get('order', len(labels)))
    return blocks


# ---------------------------------------------------------------- 表單 XML

def parse_field_values(xml_text):
    """把 FormInstance.fieldValues 拆成（一般欄位、Grid、附件）。

    邏輯對齊 BPMbackend 的 processFormFields / processGridFields /
    processAttachmentFields —— 兩邊漂移會讓同一張單在兩個系統顯示不同內容。
    純讀取，不回寫，因此不受「XML 位元組級無損」那條規則約束。
    """
    root = ET.fromstring(xml_text.strip())
    fields = {}
    grids = {}
    attachments = []

    for child in root:
        tag = child.tag
        lower = tag.lower()

        if lower == 'attachment':
            attachments.extend(_parse_attachments(child))
            continue

        if 'grid' in lower:
            records = child.find('records')
            if records is not None:
                grid_id = child.get('id') or tag
                grids[grid_id] = [
                    {item.get('id'): (item.text or '')
                     for item in record.findall('item') if item.get('id')}
                    for record in records.findall('record')
                ]
            continue

        # 一般欄位：只取葉節點的文字，與 JS 端只取 "_" 屬性的行為一致
        if len(child) == 0:
            fields[tag] = child.text or ''

    return fields, grids, attachments


def _parse_attachments(node):
    result = []
    container = node.find('attachments')
    if container is None:
        return result
    for att in container.findall('attachment'):
        result.append({
            'oid': att.get('OID') or '',
            'file_name': att.get('name') or att.get('id') or '',
            'original_file_name': att.get('originalFileName') or '',
            'file_type': att.get('fileType') or '',
            'file_size': att.get('fileSize') or '',
            'creator_name': att.get('creatorName') or '',
            'activity_name': att.get('activityName') or '',
        })
    return result
