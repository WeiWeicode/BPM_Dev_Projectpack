# -*- coding: utf-8 -*-
"""單據查詢：清單、表單內容、簽核歷程。

資料流向（實測驗證，非猜測）：

    ProcessInstance.contextOID
      → LocalRelevantData.containerOID   （id = 表單 id、valueOID = 表單實例）
      → FormInstance.OID                 （fieldValues = 表單 XML、serialNumber = 表單單號）

    ProcessInstance.contextOID
      → WorkItem.contextOID              （簽核歷程：關卡、簽核人、時間、意見）

注意 ProcessInstance.serialNumber 與 FormInstance.serialNumber 是**兩組不同編號**
（SHROT_00004620 vs E071320320），不能互相 join，也不能當成同一個「單號」。

效能上唯一的地雷是 fieldValues（ntext，55 萬列）：對它下 SQL LIKE 會全表掃描
（實測 120 秒未回）。因此自訂欄位的篩選一律先用「流程 + 日期」把候選壓小，
再在 Python 端解析 XML 比對。固定欄位（流程單號／表單單號／申請人／標題）
則走 SQL，因為那幾欄都在關聯表上。
"""

import datetime

from . import db, form_xml, settings

# ProcessInstance.currentState。4 有 abortComment 與 abortedManOID 佐證；
# 5 的最後一個 WorkItem 也是 5（流程中途被終止）。未列出的代碼原樣顯示。
PROCESS_STATE = {
    1: '進行中',
    3: '已結案',
    4: '已作廢',
    5: '已終止',
}

# WorkItem.currentState。3/4/5 有完成時間分佈佐證；
# 0/1/2 由「未完成且屬於進行中流程」加上 acceptWorkItem 必須先於 completeWorkItem
# 的順序推得（見 AGENTS.md 8.1），信心較低。
WORKITEM_STATE = {
    0: '待簽收',
    1: '處理中',
    2: '暫停',
    3: '已完成',
    4: '已作廢',
    5: '已終止',
}

# SQL Server 單次查詢的參數上限是 2100，IN 清單分批送
CHUNK = 500

BASE_SQL = """
SELECT p.OID AS processInstanceOID, p.contextOID,
       p.serialNumber AS processSerialNumber,
       p.processDefinitionId AS processId,
       p.processInstanceName AS processName,
       CAST(p.subject AS nvarchar(max)) AS subject,
       p.currentState, p.createdTime,
       u.id AS requesterId, u.userName AS requesterName,
       o.id AS orgUnitId, o.organizationUnitName AS orgUnitName,
       fi.formId, fi.formSerialNumber,
       CAST(p.abortComment AS nvarchar(max)) AS abortComment,
       au.id AS abortedById, au.userName AS abortedByName
       {form_columns}
FROM ProcessInstance p
LEFT JOIN Users u ON u.OID = p.requesterOID
LEFT JOIN OrganizationUnit o ON o.OID = p.invokeOrganizationUnitOID
LEFT JOIN Users au ON au.OID = p.abortedManOID
OUTER APPLY (
    SELECT TOP 1 l.id AS formId, f.serialNumber AS formSerialNumber{apply_columns}
    FROM LocalRelevantData l
    JOIN FormInstance f ON f.OID = l.valueOID
    WHERE l.containerOID = p.contextOID
    ORDER BY l.id
) AS fi
"""

# 用 OUTER APPLY 而不是 LEFT JOIN：一個流程的 LocalRelevantData 有多列變數
# （實測 GeneralAffairs 每張單 3 列），直接 join 會讓同一張單重複出現、
# 且沒對到表單的那幾列會多出表單單號空白的假列。實測 3 萬個 context，
# 真正指向 FormInstance 的永遠恰好 1 列，故 TOP 1 不會漏資料；
# 仍用 OUTER APPLY 而非 CROSS APPLY，讓沒掛表單的單照樣列得出來。
FORM_COLUMN = ', fi.fieldValues, fi.formDefinitionOID'
APPLY_FORM_COLUMN = (', CAST(f.fieldValues AS nvarchar(max)) AS fieldValues'
                     ', f.definitionOID AS formDefinitionOID')

# 簽核歷程。performerOID 指向 Users（不是 Employee，見 AGENTS.md 8.1）
WORKITEM_SQL = """
SELECT w.contextOID, w.workItemName, w.currentState, w.createdTime, w.completedTime,
       CAST(w.executiveComment AS nvarchar(max)) AS executiveComment,
       CAST(w.signedComment AS nvarchar(max)) AS signedComment,
       u.id AS performerId, u.userName AS performerName
FROM WorkItem w
LEFT JOIN Users u ON u.OID = w.performerOID
WHERE w.contextOID IN (%s)
ORDER BY w.createdTime, w.OID
"""


class QueryError(Exception):
    """使用者輸入造成的錯誤，由路由層轉成 400。"""


def state_name(mapping, value):
    """查不到就原樣標出代碼 —— 不編造沒實證的狀態名稱。"""
    if value is None:
        return ''
    return mapping.get(value) or ('狀態代碼 %s' % value)


def parse_date(text, field_label):
    if not text:
        raise QueryError('%s 是必填的' % field_label)
    try:
        return datetime.datetime.strptime(text.strip()[:10], '%Y-%m-%d')
    except ValueError:
        raise QueryError('%s 格式須為 YYYY-MM-DD，收到「%s」' % (field_label, text))


def date_range(start_date, end_date):
    """回傳 (起, 迄)。迄日含當天整日，故實際比較用隔日 00:00 的開區間。"""
    start = parse_date(start_date, '開始日期')
    end = parse_date(end_date, '結束日期')
    if end < start:
        raise QueryError('結束日期不得早於開始日期')
    return start, end + datetime.timedelta(days=1)


def _clean(value):
    return value.strip() if isinstance(value, str) else value


# ---------------------------------------------------------------- 主查詢

def _build_where(process_id, start, end, filters):
    """固定欄位的篩選走 SQL；全部參數化，絕不字串拼接使用者輸入。"""
    conditions = ['p.processDefinitionId = ?', 'p.createdTime >= ?', 'p.createdTime < ?']
    params = [process_id, start, end]

    filters = filters or {}
    like_map = [
        ('processSerialNumber', 'p.serialNumber'),
        ('formSerialNumber', 'fi.formSerialNumber'),
        ('subject', 'CAST(p.subject AS nvarchar(max))'),
    ]
    for key, column in like_map:
        value = (filters.get(key) or '').strip()
        if value:
            conditions.append('%s LIKE ?' % column)
            params.append('%%%s%%' % value)

    requester = (filters.get('requester') or '').strip()
    if requester:
        conditions.append('(u.id LIKE ? OR u.userName LIKE ?)')
        params.extend(['%%%s%%' % requester, '%%%s%%' % requester])

    states = filters.get('states') or []
    if states:
        conditions.append('p.currentState IN (%s)' % ','.join('?' for _ in states))
        params.extend(states)

    return ' AND '.join(conditions), params


def fetch_candidates(host, process_id, start, end, filters, with_form, limit):
    """取符合固定條件的單，最多 limit 筆。回傳 (列, 是否被上限截斷)。"""
    where, params = _build_where(process_id, start, end, filters)
    sql = ('SELECT TOP (?) * FROM (' +
           BASE_SQL.format(form_columns=FORM_COLUMN if with_form else '',
                           apply_columns=APPLY_FORM_COLUMN if with_form else '') +
           ' WHERE ' + where +
           ') AS t ORDER BY t.createdTime DESC')
    with db.connect(host) as database:
        rows = database.query(sql, tuple([limit + 1] + params))
    truncated = len(rows) > limit
    return rows[:limit], truncated


def count_candidates(host, process_id, start, end, filters):
    """只算固定條件的筆數；自訂欄位條件無法在 SQL 端算，故另外標示。"""
    where, params = _build_where(process_id, start, end, filters)
    sql = ('SELECT COUNT(*) AS c FROM (' +
           BASE_SQL.format(form_columns='', apply_columns='') +
           ' WHERE ' + where + ') AS t')
    with db.connect(host) as database:
        return database.query(sql, tuple(params))[0]['c']


def match_custom(parsed, custom_filters):
    """自訂欄位條件：全部成立才算命中（AND），值以「包含」比對，不分大小寫。"""
    for condition in custom_filters:
        field_id = condition.get('fieldId')
        wanted = (condition.get('value') or '').strip().lower()
        if not field_id or not wanted:
            continue
        actual = (parsed['fields'].get(field_id) or '').lower()
        if wanted not in actual:
            return False
    return True


def search(host, process_id, start_date, end_date, filters=None,
           custom_filters=None, page=1, page_size=None, max_rows=None):
    """查單。回傳 dict，含分頁後的列與統計。

    有自訂欄位條件時必須逐張解析表單 XML，故先用固定條件把候選壓到
    MAX_SCAN_ROWS 以內；被壓到上限就明說截斷了，不假裝這是全部。
    """
    start, end = date_range(start_date, end_date)
    page_size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    page = max(1, page or 1)
    custom_filters = [c for c in (custom_filters or [])
                      if c.get('fieldId') and (c.get('value') or '').strip()]

    if not custom_filters:
        total = count_candidates(host, process_id, start, end, filters)
        limit = min(max_rows or settings.MAX_SCAN_ROWS, page * page_size)
        rows, _ = fetch_candidates(host, process_id, start, end, filters, False, limit)
        page_rows = rows[(page - 1) * page_size: page * page_size]
        return {'rows': [summarize(r) for r in page_rows], 'total': total,
                'scanned': total, 'truncated': False, 'exact': True}

    scan_limit = max_rows or settings.MAX_SCAN_ROWS
    rows, truncated = fetch_candidates(host, process_id, start, end, filters,
                                       True, scan_limit)
    matched = []
    for row in rows:
        parsed = form_xml.safe_parse(row.get('fieldValues'))
        # 解析失敗的單一併留下並標明原因 —— 它可能正好是稽核要找的那張，
        # 用「比不出來」當作「不符合」會讓它從結果裡靜默消失。
        if parsed['error'] or match_custom(parsed, custom_filters):
            matched.append((row, parsed))
    page_rows = matched[(page - 1) * page_size: page * page_size]
    return {
        'rows': [summarize(row, parsed) for row, parsed in page_rows],
        'total': len(matched),
        'scanned': len(rows),
        'truncated': truncated,
        'exact': not truncated,
    }


def summarize(row, parsed=None):
    """一列單頭。狀態一律附上可讀名稱，代碼查不到就標代碼本身。"""
    summary = {
        'processInstanceOID': _clean(row.get('processInstanceOID')),
        'contextOID': _clean(row.get('contextOID')),
        'processSerialNumber': _clean(row.get('processSerialNumber')) or '',
        'formSerialNumber': _clean(row.get('formSerialNumber')) or '',
        'processId': _clean(row.get('processId')) or '',
        'processName': _clean(row.get('processName')) or '',
        'formId': _clean(row.get('formId')) or '',
        'subject': (row.get('subject') or '').strip(),
        'state': row.get('currentState'),
        'stateName': state_name(PROCESS_STATE, row.get('currentState')),
        'createdTime': row.get('createdTime'),
        'requesterId': _clean(row.get('requesterId')) or '',
        'requesterName': _clean(row.get('requesterName')) or '',
        'orgUnitId': _clean(row.get('orgUnitId')) or '',
        'orgUnitName': _clean(row.get('orgUnitName')) or '',
        'abortComment': (row.get('abortComment') or '').strip(),
        'abortedBy': _clean(row.get('abortedByName')) or '',
        'parseError': '',
    }
    if parsed is not None:
        summary['parseError'] = parsed.get('error') or ''
    return summary


# ---------------------------------------------------------------- 簽核歷程

def work_items(host, context_oids):
    """{contextOID: [關卡...]}。依建立時間排序，即實際流轉順序。"""
    result = {}
    oids = [o for o in context_oids if o]
    if not oids:
        return result
    with db.connect(host) as database:
        for index in range(0, len(oids), CHUNK):
            chunk = oids[index:index + CHUNK]
            sql = WORKITEM_SQL % ','.join('?' for _ in chunk)
            for row in database.query(sql, tuple(chunk)):
                context = _clean(row['contextOID'])
                result.setdefault(context, []).append({
                    'workItemName': _clean(row.get('workItemName')) or '',
                    'state': row.get('currentState'),
                    'stateName': state_name(WORKITEM_STATE, row.get('currentState')),
                    'createdTime': row.get('createdTime'),
                    'completedTime': row.get('completedTime'),
                    'performerId': _clean(row.get('performerId')) or '',
                    'performerName': _clean(row.get('performerName')) or '',
                    'comment': ((row.get('executiveComment') or '').strip() or
                                (row.get('signedComment') or '').strip()),
                })
    return result


def progress(items):
    """由簽核歷程算出時程摘要：結案時間、目前關卡、待辦人、已簽關卡數。

    ProcessInstance 沒有結案時間欄位，故以最後一個關卡的完成時間為準；
    還有未完成關卡時就代表沒結案，這時不給結案時間。
    """
    completed = [i for i in items if i['completedTime']]
    pending = [i for i in items if not i['completedTime']]
    last = max(completed, key=lambda i: i['completedTime']) if completed else None
    return {
        'closedTime': None if pending else (last['completedTime'] if last else None),
        'completedSteps': len(completed),
        'totalSteps': len(items),
        'currentStep': pending[0]['workItemName'] if pending else '',
        'currentPerformer': ('%s %s' % (pending[0]['performerId'],
                                        pending[0]['performerName'])).strip()
                            if pending else '',
        'lastSigner': ('%s %s' % (last['performerId'], last['performerName'])).strip()
                      if last else '',
        'lastSignedTime': last['completedTime'] if last else None,
    }


# ---------------------------------------------------------------- 單張單

def load_instance(host, process_serial_number):
    """單張單的完整內容：單頭 + 表單欄位值 + 表格明細 + 簽核歷程。

    以流程單號查（表單單號是另一組編號，不能拿來當這裡的鍵）。
    """
    sql = (BASE_SQL.format(form_columns=FORM_COLUMN,
                           apply_columns=APPLY_FORM_COLUMN) +
           ' WHERE p.serialNumber = ?')
    with db.connect(host) as database:
        rows = database.query(sql, (process_serial_number,))
    if not rows:
        return None
    row = rows[0]
    parsed = form_xml.safe_parse(row.get('fieldValues'))
    context = _clean(row.get('contextOID'))
    items = work_items(host, [context]).get(context, [])
    return {
        'summary': summarize(row, parsed),
        'parsed': parsed,
        'items': items,
        'progress': progress(items),
        # 這張單當時用的那一版表單定義；欄位名稱要用它，不是表單的最新版
        'formDefinitionOID': _clean(row.get('formDefinitionOID')) or '',
    }


def values_for_serials(host, serial_numbers, field_ids):
    """一次撈多張單的指定欄位值，供表格顯示自訂欄位用。

    刻意不逐張 load_instance —— 一頁 50 筆就會變成 50 次查詢。
    """
    values = {}
    serials = [s for s in serial_numbers if s]
    if not serials or not field_ids:
        return values
    sql = ('SELECT p.serialNumber AS sn, fi.fieldValues '
           'FROM ProcessInstance p '
           'OUTER APPLY ('
           '  SELECT TOP 1 CAST(f.fieldValues AS nvarchar(max)) AS fieldValues '
           '  FROM LocalRelevantData l '
           '  JOIN FormInstance f ON f.OID = l.valueOID '
           '  WHERE l.containerOID = p.contextOID ORDER BY l.id) AS fi '
           'WHERE p.serialNumber IN (%s)')
    with db.connect(host) as database:
        for index in range(0, len(serials), CHUNK):
            chunk = serials[index:index + CHUNK]
            rows = database.query(sql % ','.join('?' for _ in chunk), tuple(chunk))
            for row in rows:
                parsed = form_xml.safe_parse(row.get('fieldValues'))
                values[_clean(row['sn'])] = {
                    fid: parsed['fields'].get(fid, '') for fid in field_ids}
    return values
