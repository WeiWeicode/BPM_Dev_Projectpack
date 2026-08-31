# -*- coding: utf-8 -*-
"""關卡操作：看歷程 → 模擬該關卡的人 → 簽收 → 改表單 → 簽核推進 / 轉派 / 取回 / 收單。

**為什麼要「模擬該關卡的使用者」**：這組 API 沒有登入概念，操作者一律由參數指定，
而且指定錯了會被擋（`acceptWorkItem` 的 pUserId 必須是待辦目前擁有者、
`assigneeReassignWorkItem` 的 pRequesterOID 必須是目前擁有者）。
所以這裡先從簽核歷程解析出目前關卡的待辦人，再以那個人的身分送出，
使用者不必自己去查是誰、也不必自己記 OID。

實測（quickDevTestProcessImportWebTool00000002）確認的順序與語意：

    checkWorkItemState  0 = 未簽收，1 = 已簽收
    未簽收就 completeWorkItem → "The workitem is not running state"
    accept → （可順便改表單）→ complete → 流程前進到下一關
    reexecuteActivity   目前關卡變 closed.terminated，被取回的關卡重新 open

**員工編號要對到 Users.OID，不是 Employee.OID**（AGENTS.md 8.1）。轉派的
pAcceptorOID / pRequesterOID 都是前者，餵錯會回 "Can't find User. By OID = …"。
這個對照只能查資料庫，查不到就把轉派功能標成不可用，不猜。
"""

import sys
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import ws_client
from . import form_edit, settings

# performerName 的格式是「員工編號_姓名」，實測如 S093013_林吟霞
PERFORMER_SEP = '_'

# 這些狀態代表關卡還在跑，會有待辦
OPEN_PREFIX = 'open.'


class WorkItemError(Exception):
    """關卡操作的預期內錯誤，由路由層轉成 400。"""


def _client(endpoint: Optional[str] = None) -> ws_client.WorkflowService:
    target = endpoint or settings.DEFAULT_ENDPOINT
    if '10.10.130.190' in target:
        raise WorkItemError('190 正式區永久禁止連線（AGENTS.md 規則 8.1）')
    return ws_client.WorkflowService(endpoint=target,
                                     api_path=settings.API_JSON_PATH)


# ── 員工編號 → Users.OID ────────────────────────────────────────

class UserOidIndex(object):
    """查 Users.OID。轉派非用它不可，但整頁不該因為查不到就掛掉。

    刻意只 SELECT OID / id / userName —— Users 表同時存著 password 欄，
    不需要的欄位一律不撈，免得無意間把密碼帶進 API 回應或日誌。
    """

    def __init__(self):
        self._cache: Dict[str, Optional[str]] = {}
        self._names: Dict[str, str] = {}
        self._unavailable: Optional[str] = None

    def _database(self):
        if settings.DB_EXPLORER_DIR not in sys.path:
            sys.path.insert(0, settings.DB_EXPLORER_DIR)
        from bpm_kb import db  # noqa: E402
        return db

    def lookup(self, user_ids: List[str]) -> Dict[str, Any]:
        """回傳 {'oids': {員工編號: OID}, 'names': {...}, 'source': 說明}。"""
        wanted = [uid for uid in dict.fromkeys(user_ids) if uid]
        if not wanted:
            return {'oids': {}, 'names': {}, 'source': '沒有要查的員工編號'}

        missing = [uid for uid in wanted if uid not in self._cache]
        if missing and not self._unavailable:
            try:
                db = self._database()
                marks = ','.join('?' for _ in missing)
                with db.Database() as database:
                    rows = database.query(
                        'SELECT OID, id, userName FROM Users WHERE id IN (%s)' % marks,
                        tuple(missing))
                found = dict(((r['id'] or '').strip(), r) for r in rows)
                for uid in missing:
                    row = found.get(uid)
                    self._cache[uid] = (row['OID'] or '').strip() if row else None
                    if row:
                        self._names[uid] = (row['userName'] or '').strip()
            except ImportError as err:
                self._unavailable = '未安裝 bpm_kb 的相依套件（%s），轉派功能不可用' % err
            except Exception as err:
                self._unavailable = '無法連線唯讀資料庫（%s: %s），轉派功能不可用' % (
                    type(err).__name__, str(err)[:120])

        if self._unavailable:
            return {'oids': {}, 'names': {}, 'source': self._unavailable}
        return {
            'oids': dict((uid, self._cache.get(uid)) for uid in wanted),
            'names': dict((uid, self._names.get(uid)) for uid in wanted),
            'source': 'Users 表（唯讀查詢）',
        }


user_oid_index = UserOidIndex()


# ── 讀關卡與待辦 ────────────────────────────────────────────────

def _performer_ids(text: str) -> List[str]:
    """把 'S093013_林吟霞' 或 'S095006_林正勛, S100026_葉韻綾' 拆成員工編號。"""
    ids = []
    for part in (text or '').split(','):
        part = part.strip()
        if not part:
            continue
        ids.append(part.split(PERFORMER_SEP, 1)[0].strip() if PERFORMER_SEP in part else part)
    return ids


def _todo_of(service: ws_client.WorkflowService, process_id: str,
             user_id: str, serial_no: str) -> Optional[Dict[str, str]]:
    """查某人在這張單上的待辦。查不到回 None —— 非當前簽核者本來就是空清單。"""
    try:
        raw = service.call('fetchToDoWorkItem', pProcessIds=process_id, pUserId=user_id)
    except ws_client.SoapFault:
        return None
    if not raw:
        return None
    for element in ET.fromstring(raw).iter():
        if not element.tag.endswith('SimpleWorkItem'):
            continue
        if element.findtext('processSerialNumber') != serial_no:
            continue
        return {
            'workItemOID': element.findtext('workItemOID'),
            'activityId': element.findtext('activityId'),
        }
    return None


def load_activities(serial_no: str,
                    endpoint: Optional[str] = None) -> Dict[str, Any]:
    """關卡歷程 + 目前關卡的待辦人與工作項目 OID。

    工作項目 OID 只有 fetchToDoWorkItem 查得到，而它要先知道是誰 ——
    所以先從歷程解析出目前關卡的 performerName，再逐人去查。
    """
    if not serial_no or not serial_no.strip():
        raise WorkItemError('請輸入單號')
    serial_no = serial_no.strip()

    service = _client(endpoint)
    started = time.time()
    try:
        raw = service.call('fetchFullProcInstanceWithSerialNo',
                           pProcessInstanceSerialNo=serial_no)
    except ws_client.SoapFault as fault:
        raise WorkItemError('查不到單號 %s：%s' % (serial_no, fault.message))

    header = service.call('fetchProcInstanceWithSerialNo',
                          pProcessInstanceSerialNo=serial_no)
    header_root = ET.fromstring(header)
    process_id = header_root.findtext('processId') or ''
    process_state = header_root.findtext('state') or ''

    activities: List[Dict[str, Any]] = []
    for node in ET.fromstring(raw).iter():
        if not node.tag.endswith('ActInstanceInfo'):
            continue
        details = [d for d in node.iter() if d.tag.endswith('PerformDetail')]
        performers, notified, comments = [], [], []
        for detail in details:
            performers.extend(_performer_ids(detail.findtext('performerName')))
            notified.extend(_performer_ids(detail.findtext('notifiedName')))
            comment = (detail.findtext('comment') or '').strip()
            if comment:
                comments.append(comment)
        state = node.findtext('state') or ''
        activities.append({
            'activityId': node.findtext('activityId'),
            'activityName': node.findtext('activityName'),
            'state': state,
            'startedTime': node.findtext('startedTime'),
            'performType': node.findtext('performType'),
            'performerIds': performers,
            'notifiedIds': notified,
            'comments': comments,
            'running': state.startswith(OPEN_PREFIX),
        })

    # 只有還在跑的關卡才有待辦；一關可能多人（並簽）
    current: List[Dict[str, Any]] = []
    for activity in activities:
        if not activity['running']:
            continue
        for user_id in activity['performerIds']:
            todo = _todo_of(service, process_id, user_id, serial_no)
            current.append({
                'userId': user_id,
                'activityId': activity['activityId'],
                'activityName': activity['activityName'],
                'workItemOID': todo['workItemOID'] if todo else None,
                'accepted': None,
            })

    lookup = user_oid_index.lookup([c['userId'] for c in current])
    for entry in current:
        entry['usersOid'] = lookup['oids'].get(entry['userId'])
        entry['userName'] = lookup['names'].get(entry['userId'])
        if entry['workItemOID']:
            try:
                state = service.call('checkWorkItemState',
                                     pWorkItemOID=entry['workItemOID'])
                entry['workItemState'] = (state or '').strip()
                entry['accepted'] = (state or '').strip() == '1'
            except ws_client.SoapFault:
                entry['workItemState'] = None

    return {
        'serialNo': serial_no,
        'processId': process_id,
        'processName': header_root.findtext('processName'),
        'subject': header_root.findtext('subject'),
        'processState': process_state,
        'closed': process_state.startswith('closed.'),
        'activities': activities,
        'currentPerformers': current,
        'oidSource': lookup['source'],
        'reassignAvailable': bool(lookup['oids']) and all(lookup['oids'].values()),
        'elapsedMs': int((time.time() - started) * 1000),
    }


# ── 關卡操作 ────────────────────────────────────────────────────

def accept(work_item_oid: str, user_id: str, confirm: bool = False,
           endpoint: Optional[str] = None) -> Dict[str, Any]:
    """簽收待辦。pUserId 必須是待辦目前擁有者，傳別人會被拒絕。"""
    if not confirm:
        raise WorkItemError('簽收會改變待辦狀態，必須確認後才能送出。')
    if not work_item_oid or not user_id:
        raise WorkItemError('缺少工作項目 OID 或簽收者')

    service = _client(endpoint)
    started = time.time()
    try:
        service.call('acceptWorkItem', pWorkItemOID=work_item_oid, pUserId=user_id)
    except ws_client.SoapFault as fault:
        raise WorkItemError('簽收失敗：%s' % fault.message)

    state = service.call('checkWorkItemState', pWorkItemOID=work_item_oid)
    return {
        'status': 'ok',
        'workItemState': (state or '').strip(),
        'accepted': (state or '').strip() == '1',
        'elapsedMs': int((time.time() - started) * 1000),
        'message': '%s 已簽收（checkWorkItemState=%s，1 表示已簽收）。' % (user_id, state),
    }


def complete(serial_no: str, work_item_oid: str, user_id: str,
             comment: str = '', changes: Optional[Dict[str, str]] = None,
             auto_accept: bool = True, confirm: bool = False,
             endpoint: Optional[str] = None) -> Dict[str, Any]:
    """（可選）先改表單，再簽核推進到下一關。

    auto_accept 預設開啟：實測未簽收就簽核一定失敗於
    "The workitem is not running state"，這個順序在 WSDL 上完全看不出來，
    與其讓使用者自己踩，不如先簽收。已簽收的再簽收一次不影響。
    """
    if not confirm:
        raise WorkItemError('簽核會推動流程到下一關且無法復原，必須確認後才能送出。')
    if not work_item_oid or not user_id:
        raise WorkItemError('缺少工作項目 OID 或簽核者')

    service = _client(endpoint)
    started = time.time()
    steps: List[Dict[str, Any]] = []

    form_result = None
    if changes:
        # 借用改單那一套：讀回現值、只換目標欄位、整份寫回、再讀回比對
        form_result = form_edit.submit_changes(serial_no, changes=changes,
                                               confirm=True, endpoint=endpoint)
        steps.append({'step': 'updateFormValueBySerialNember',
                      'ok': form_result['verified'],
                      'detail': form_result['message']})
        if not form_result['verified']:
            raise WorkItemError('表單寫入後讀回比對失敗，已中止簽核，流程未被推動。'
                                '請先確認欄位值：%s' % form_result['message'])

    if auto_accept:
        # 先問狀態再決定要不要簽收：對已簽收的待辦再送一次 acceptWorkItem 會回
        # "The workitem has been performed"，那是正常情況，不該當成失敗顯示。
        try:
            state = (service.call('checkWorkItemState',
                                  pWorkItemOID=work_item_oid) or '').strip()
        except ws_client.SoapFault:
            state = ''
        if state == '1':
            steps.append({'step': 'acceptWorkItem', 'ok': True,
                          'detail': '已是簽收狀態，略過簽收'})
        else:
            try:
                service.call('acceptWorkItem', pWorkItemOID=work_item_oid,
                             pUserId=user_id)
                steps.append({'step': 'acceptWorkItem', 'ok': True, 'detail': '已簽收'})
            except ws_client.SoapFault as fault:
                steps.append({'step': 'acceptWorkItem', 'ok': False,
                              'detail': fault.message})

    try:
        service.call('completeWorkItem', pWorkItemOID=work_item_oid,
                     pUserId=user_id, pComment=comment or '')
        steps.append({'step': 'completeWorkItem', 'ok': True, 'detail': '已簽核'})
    except ws_client.SoapFault as fault:
        raise WorkItemError('簽核失敗：%s（表單若已寫入則保持寫入後的狀態）'
                            % fault.message)

    after = load_activities(serial_no, endpoint)
    return {
        'status': 'ok',
        'steps': steps,
        'formResult': form_result,
        'after': after,
        'elapsedMs': int((time.time() - started) * 1000),
        'message': '已簽核。目前關卡：%s' % (
            '、'.join('%s（%s）' % (c['activityName'] or c['activityId'], c['userId'])
                     for c in after['currentPerformers']) or '流程已結束'),
    }


def reassign(work_item_oid: str, acceptor_id: str, comment: str = '',
             mode: str = 'management', requester_id: str = '',
             confirm: bool = False,
             endpoint: Optional[str] = None) -> Dict[str, Any]:
    """轉派待辦。

    mode='management' 走 managementReassignWorkItem（管理者強制，不需目前擁有者同意）
    mode='assignee'   走 assigneeReassignWorkItem（簽核者自行轉派，
                      pRequesterOID 必須是**待辦目前擁有者**，不是原申請人）
    mode='owner'      走 managementChangeWorkItemOwner（變更擁有者）
    """
    if not confirm:
        raise WorkItemError('轉派會把待辦換到別人名下，必須確認後才能送出。')
    if not work_item_oid or not acceptor_id:
        raise WorkItemError('缺少工作項目 OID 或接收者')

    needed = [acceptor_id] + ([requester_id] if mode == 'assignee' else [])
    lookup = user_oid_index.lookup(needed)
    if not lookup['oids']:
        raise WorkItemError('無法取得 Users.OID：%s' % lookup['source'])
    acceptor_oid = lookup['oids'].get(acceptor_id)
    if not acceptor_oid:
        raise WorkItemError('Users 表查不到 %s，轉派需要 Users.OID' % acceptor_id)

    service = _client(endpoint)
    started = time.time()
    if mode == 'assignee':
        requester_oid = lookup['oids'].get(requester_id)
        if not requester_oid:
            raise WorkItemError('Users 表查不到目前擁有者 %s' % requester_id)
        params = {'pRequesterOID': requester_oid, 'pAcceptorOID': acceptor_oid,
                  'pWorkItemOID': work_item_oid, 'pReassignComment': comment or ''}
        method = 'assigneeReassignWorkItem'
    elif mode == 'owner':
        params = {'pAcceptorOID': acceptor_oid, 'pWorkItemOID': work_item_oid,
                  'pReassignComment': comment or ''}
        method = 'managementChangeWorkItemOwner'
    else:
        params = {'pAcceptorOID': acceptor_oid, 'pWorkItemOID': work_item_oid,
                  'pReassignComment': comment or ''}
        method = 'managementReassignWorkItem'

    try:
        service.call(method, **params)
    except ws_client.SoapFault as fault:
        raise WorkItemError('轉派失敗（%s）：%s' % (method, fault.message))

    return {
        'status': 'ok',
        'method': method,
        'acceptorId': acceptor_id,
        'acceptorOid': acceptor_oid,
        'elapsedMs': int((time.time() - started) * 1000),
        'message': '已用 %s 把待辦轉給 %s。' % (method, acceptor_id),
    }


def reexecute(serial_no: str, ask_user_id: str, activity_id: str,
              comment: str = '', confirm: bool = False,
              endpoint: Optional[str] = None) -> Dict[str, Any]:
    """取回重辦：把已簽核的關卡叫回來重新處理。

    實測效果：目前進行中的關卡變 closed.terminated，
    被取回的關卡重新 open.running，待辦回到原簽核者手上。
    """
    if not confirm:
        raise WorkItemError('取回重辦會終止目前關卡並讓流程倒退，必須確認後才能送出。')
    if not serial_no or not activity_id or not ask_user_id:
        raise WorkItemError('缺少單號、關卡 id 或提出取回的人')

    service = _client(endpoint)
    started = time.time()
    try:
        service.call('reexecuteActivity', pProcessSerialNo=serial_no,
                     pAskReexecuteUserId=ask_user_id,
                     pReexecuteActivityId=activity_id,
                     pReexecuteComment=comment or '')
    except ws_client.SoapFault as fault:
        raise WorkItemError('取回重辦失敗：%s' % fault.message)

    after = load_activities(serial_no, endpoint)
    return {
        'status': 'ok',
        'after': after,
        'elapsedMs': int((time.time() - started) * 1000),
        'message': '已取回關卡 %s。目前關卡：%s' % (activity_id,
            '、'.join('%s（%s）' % (c['activityName'] or c['activityId'], c['userId'])
                     for c in after['currentPerformers']) or '（無）'),
    }


def close_process(serial_no: str, mode: str = 'abort', user_id: str = '',
                  comment: str = '', confirm: bool = False,
                  endpoint: Optional[str] = None) -> Dict[str, Any]:
    """收單：作廢或終止整張單。

    兩者差在最終 state（closed.aborted vs closed.terminated）。
    作廢不需要操作者參數，終止需要 —— 這是 WSDL 上就看得出的差別，
    但「終止在某些單上回 IllegalArgumentException 而作廢可以」是實測才知道的，
    所以失敗時把另一條路寫在錯誤訊息裡。
    """
    if not confirm:
        raise WorkItemError('收單會把整張單關掉且無法復原，必須確認後才能送出。')
    if not serial_no:
        raise WorkItemError('缺少單號')

    service = _client(endpoint)
    started = time.time()
    if mode == 'terminate':
        if not user_id:
            raise WorkItemError('終止需要指定操作者（pUserId）')
        method, params = 'terminatedProcessForSerialNo', {
            'pProcessInstanceSerialNo': serial_no, 'pUserId': user_id,
            'pTerminatedComment': comment or ''}
        hint = '若回 IllegalArgumentException，改用「作廢」通常可行（實測結果）。'
    else:
        method, params = 'abortProcessForSerialNo', {
            'pProcessInstanceSerialNo': serial_no, 'pAbortComment': comment or ''}
        hint = ''

    try:
        service.call(method, **params)
    except ws_client.SoapFault as fault:
        raise WorkItemError('%s 失敗：%s %s' % (method, fault.message, hint))

    header = service.call('fetchProcInstanceWithSerialNo',
                          pProcessInstanceSerialNo=serial_no)
    state = ET.fromstring(header).findtext('state')
    saved_comment = None
    try:
        saved_comment = service.call('fetchProcessAbortOrTerminateComment',
                                     pProcessSerialNo=serial_no)
    except ws_client.SoapFault:
        pass

    return {
        'status': 'ok',
        'method': method,
        'processState': state,
        'savedComment': saved_comment,
        'elapsedMs': int((time.time() - started) * 1000),
        'message': '已%s，單據狀態 %s。' % ('終止' if mode == 'terminate' else '作廢', state),
    }
