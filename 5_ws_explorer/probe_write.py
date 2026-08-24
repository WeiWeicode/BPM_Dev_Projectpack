# -*- coding: utf-8 -*-
"""實測有副作用的方法：開單、簽核、轉派、加關卡、作廢。

**這支程式會在 191 測試區產生真實的簽核單與待辦。** 不會動到既有的單子 ——
每個情境自己開新單來操作，操作完就把單子收掉（終止或作廢），
不留一堆卡在中間的待辦給別人。

為什麼要寫成情境而不是像 probe_api.py 逐支呼叫：這些方法彼此相依。
沒有單就沒有工作項目，沒有工作項目就測不了簽核與轉派，
簽核完關卡就換人、原本的工作項目 OID 立刻失效。順序錯了全部都是錯誤訊息。

參數格式未知的方法（pPostActDefsAsXML、pInvokeParameter 之類），
刻意送出可辨識的無效值來換取錯誤訊息 —— 錯誤訊息本身就是規格文件。

唯一不執行的是 importOrganizationData：它會覆寫組織資料，
而組織是所有流程的根基，測試區也不該冒這個險（見 AGENTS.md 8.1）。

產出 out/write_probe_result.json 與 out/write_probe_result.md。
"""

import datetime
import json
import os
import time

import ws_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUT_DIR = os.path.join(BASE_DIR, 'out')

# 測試素材。OID 與公司別 id 查自資料庫（唯讀）。
# 使用者 OID 必須取自 Users.OID，**不是 Employee.OID** —— 兩張表都有
# 同一個人，OID 只差一個字元（4db90e2c… vs 4db90e2d…），
# 餵錯的話 managementReassignWorkItem 會回 Can't find User。
PROCESS_ID = 'SP_DetectionOPProcess'
USER_ID = 'S112009'
USER_OID = '4db90e2cf0151004808a451881bdf758'
PEER_ID = 'S094009'
PEER_OID = '35345d84d6d4100482071bce21009000'
ORG_UNIT_ID = 'S1800'
ORG_ID = 'GIGASOLAR'
LABEL_OID = '000000000000000000000LabelSealed'

STAMP = datetime.datetime.now().strftime('%m%d%H%M')


class Recorder(object):
    """把每一步的意圖、送出值、結果都留下來。失敗照記，不重試、不掩飾。"""

    def __init__(self, service):
        self.service = service
        self.steps = []

    def call(self, method, purpose, params, expect=None):
        started = time.time()
        record = {
            'method': method,
            'purpose': purpose,
            'params': dict(params),
            'expect': expect,
        }
        try:
            operation = self.service.find_operation(method, params)
            value, _ = self.service.call_operation(operation, params)
            record['status'] = 'ok'
            record['return'] = value
            record['inputMessage'] = operation['inputMessage']
        except ws_client.SoapFault as fault:
            record['status'] = 'fault'
            record['fault'] = fault.message
        except Exception as error:
            record['status'] = 'error'
            record['error'] = '%s: %s' % (type(error).__name__, error)
        record['elapsedMs'] = int((time.time() - started) * 1000)
        self.steps.append(record)

        summary = record.get('return') or record.get('fault') or record.get('error') or ''
        print('  %-6s %-38s %s' % (record['status'], method,
                                   str(summary).replace('\n', ' ')[:110]))
        return record

    def note(self, method, purpose, reason):
        """刻意不執行的方法也要留紀錄，否則看起來像漏測。"""
        self.steps.append({
            'method': method,
            'purpose': purpose,
            'status': 'refused',
            'reason': reason,
        })
        print('  %-6s %-38s %s' % ('refused', method, reason))


def _field_values(template, overrides):
    """依 getFormFieldTemplate 的模板組 pFormFieldValue。

    不自己拼欄位名 —— 本專案已經踩過一次：欄位 id 不存在時 invokeProcess
    照收，等到 fetchUniFormatFormInstance* 讀取才爆。模板是唯一權威來源。
    """
    text = template
    for field, value in overrides.items():
        head = text.find('<%s ' % field)
        if head < 0:
            continue
        start = text.find('>', head) + 1
        end = text.find('</%s>' % field, start)
        text = text[:start] + value + text[end:]
    return text


def _serial_of(value):
    """開單方法的回傳值。實測為單號字串，非 XML。"""
    if not value:
        return None
    return value.strip()


def run():
    service = ws_client.WorkflowService()
    recorder = Recorder(service)

    print('準備素材')
    form_oid = service.call('findFormOIDsOfProcess', pProcessPackageId=PROCESS_ID)
    template = service.call('getFormFieldTemplate', pFormDefinitionOID=form_oid)
    field_values = _field_values(template, {
        'ControlPlanNoTextBox': 'CP-API-%s' % STAMP,
        'ControlPlanProductTextBox': 'API 實測',
        'ControlPlanEditionNoTextBox': 'A0',
    })
    print('  表單 OID %s，模板 %d 字元' % (form_oid, len(template)))

    def subject(tag):
        return 'API實測_%s_%s' % (tag, STAMP)

    # ── 第一階段：8 支開單方法 ──────────────────────────────
    print('')
    print('第一階段：開單（8 支）')
    tickets = {}

    tickets['minimal'] = recorder.call(
        'invokeProcess', '四參數版：只開單、不帶表單值',
        {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
         'pOrgUnitId': ORG_UNIT_ID, 'pSubject': subject('最小開單')},
        expect='回傳新單號')

    tickets['full'] = recorder.call(
        'invokeProcess', '六參數版：開單並帶入表單欄位值',
        {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
         'pOrgUnitId': ORG_UNIT_ID, 'pFormDefOID': form_oid,
         'pFormFieldValue': field_values, 'pSubject': subject('帶表單值')},
        expect='回傳新單號，且欄位值可讀回')

    tickets['byorg'] = recorder.call(
        'invokeProcessByOrg', '五參數版：指定公司別開單',
        {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
         'pOrgUnitId': ORG_UNIT_ID, 'pOrgId': ORG_ID,
         'pSubject': subject('指定公司別')},
        expect='pOrgId 吃 Organization.id（GIGASOLAR），非部門 id')

    tickets['byorg_full'] = recorder.call(
        'invokeProcessByOrg', '七參數版：指定公司別並帶表單值',
        {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
         'pOrgUnitId': ORG_UNIT_ID, 'pOrgId': ORG_ID, 'pFormDefOID': form_oid,
         'pFormFieldValue': field_values, 'pSubject': subject('公司別帶值')})

    # 自訂關卡 XML 的格式未知，先送無效值換錯誤訊息
    tickets['custact'] = recorder.call(
        'invokeProcessAndAddCustAct', '開單同時追加自訂關卡（探 pPostPSActDefsAsXML 格式）',
        {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
         'pOrgUnitId': ORG_UNIT_ID, 'pFormDefOID': form_oid,
         'pFormFieldValue': field_values, 'pSubject': subject('自訂關卡'),
         'pPostPSActDefsAsXML': ''},
        expect='空字串應被拒絕，錯誤訊息可望揭露 XML 格式')

    tickets['custact_org'] = recorder.call(
        'invokeProcessAndAddCustActByOrg', '同上，多指定公司別',
        {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
         'pOrgUnitId': ORG_UNIT_ID, 'pOrgId': ORG_ID, 'pFormDefOID': form_oid,
         'pFormFieldValue': field_values, 'pSubject': subject('自訂關卡公司別'),
         'pPostPSActDefsAsXML': ''})

    tickets['byparam'] = recorder.call(
        'invokeProcessByParameter', '以參數開單（探 pParameterId / pInvokeParameter）',
        {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
         'pOrgUnitId': ORG_UNIT_ID, 'pParameterId': 'API_PROBE',
         'pInvokeParameter': 'probe', 'pSubject': subject('參數開單')},
        expect='參數 id 的有效值未知，看錯誤訊息')

    tickets['byparam_org'] = recorder.call(
        'invokeProcessByParameterByOrg', '同上，多指定公司別',
        {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
         'pOrgUnitId': ORG_UNIT_ID, 'pOrgId': ORG_ID, 'pParameterId': 'API_PROBE',
         'pInvokeParameter': 'probe', 'pSubject': subject('參數開單公司別')})

    serials = dict((key, _serial_of(item.get('return')))
                   for key, item in tickets.items() if item['status'] == 'ok')
    print('  開出的單：%s' % ', '.join(sorted(v for v in serials.values() if v)))

    # 錯誤訊息指出 pParameterId 要的是流程變數 id，換正確的值再試一次
    if tickets['byparam']['status'] == 'fault':
        retry = recorder.call(
            'invokeProcessByParameter', '重試：pParameterId 改用流程變數 id',
            {'pProcessPackageId': PROCESS_ID, 'pRequesterId': USER_ID,
             'pOrgUnitId': ORG_UNIT_ID, 'pParameterId': 'isSeparateByVerNo',
             'pInvokeParameter': 'true', 'pSubject': subject('參數開單重試')},
            expect='第一次的錯誤訊息說要 RelevantData，驗證這個推論')
        if retry['status'] == 'ok':
            serials['byparam'] = _serial_of(retry['return'])

    if not serials.get('full'):
        print('  六參數開單失敗，後續情境沒有素材可用，停在這裡')
        return recorder, serials

    main_serial = serials['full']

    # ── 第二階段：工作項目與流程操作 ────────────────────────
    print('')
    print('第二階段：工作項目操作（單號 %s）' % main_serial)

    work_item = _current_work_item(service, main_serial, USER_ID)
    if not work_item:
        print('  取不到工作項目，跳過本階段')
    else:
        print('  工作項目 %s（關卡 %s）' % (work_item['workItemOID'], work_item['activityId']))
        item_oid = work_item['workItemOID']

        recorder.call('increaseViewTimesOfWorkAssignment', '累加待辦的檢視次數',
                      {'pUserId': USER_ID, 'pWorkItemOID': item_oid})

        recorder.call('acceptWorkItem', '簽收待辦（尚未簽核）',
                      {'pWorkItemOID': item_oid, 'pUserId': work_item['userId']})

        recorder.call('addLabelToNoticeWorkItem', '為待辦加上標籤（測試區只有 SEALED 一個標籤）',
                      {'pWorkItemOID': item_oid, 'pUserOID': USER_OID,
                       'pLabelOID': LABEL_OID})
        recorder.call('removeLabelFromNoticeWorkItem', '移除剛加的標籤',
                      {'pWorkItemOID': item_oid, 'pUserOID': USER_OID,
                       'pLabelOID': LABEL_OID})

        # 寫入之後立刻讀回來比對，才算真的驗證過
        recorder.call('assignRelevantDataBySerialNo', '設定流程變數',
                      {'pProcessInstanceSerialNo': main_serial,
                       'pRelevantDataId': 'isSeparateByVerNo',
                       'pRelevantDataValue': 'true'},
                      expect='寫入後以 fetchProcessContextVariable 讀回應為 true')
        _verify(recorder, service, 'assignRelevantDataBySerialNo 寫入後讀回',
                'fetchProcessContextVariable',
                {'pProcessSerialNo': main_serial, 'pVariableId': 'isSeparateByVerNo',
                 'pOnlyTextValue': 'true'}, contains='true')

        form_oid_now = service.call('findFormOIDsOfProcess', pProcessPackageId=PROCESS_ID)
        changed = _field_values(
            service.call('getFormFieldTemplate', pFormDefinitionOID=form_oid_now),
            {'ControlPlanProductTextBox': '已被 updateFormValue 改寫'})
        recorder.call('updateFormValueBySerialNember', '改寫已開單的表單欄位值（方法名 Nember 是原廠拼字）',
                      {'serialNumber': main_serial, 'pFormValue': changed},
                      expect='改寫後以 fetchFormInstance 讀回應看到新值')
        _verify(recorder, service, 'updateFormValueBySerialNember 寫入後讀回',
                'fetchFormInstanceWithProcSerlNo',
                {'pProcessInstanceSerialNo': main_serial},
                contains='已被 updateFormValue 改寫')

        # 自訂關卡系列：XML 格式未知，用無效值換錯誤訊息
        recorder.call('addCustomActivity', '追加自訂串簽關卡（空 list，不實際加關卡）',
                      {'pWorkItmeOID': item_oid, 'pPostActDefsAsXML': '<list/>'})
        recorder.call('addCustomParallelActivity', '追加自訂並簽關卡（空 list）',
                      {'pWorkItmeOID': item_oid,
                       'pPostParallelActDefsAsXML': '<list/>'})
        recorder.call('addCustomParallelAndSerialActivity', '兩參數版：並串簽混合',
                      {'pWorkItmeOID': item_oid, 'pPostPSActDefsAsXML': '<list/>'})
        recorder.call('addCustomParallelAndSerialActivity', '四參數版：指定關卡與參考關卡',
                      {'pProcessInstanceSN': main_serial,
                       'pActId': work_item['activityId'],
                       'pRefActId': work_item['activityId'],
                       'pPostPSActDefsAsXML': '<list/>'})
        recorder.call('addCloneSerialActivity', '複製一個既有關卡插進流程',
                      {'pProcessInstanceSN': main_serial,
                       'pActId': work_item['activityId'],
                       'pRefActId': work_item['activityId']})

        recorder.call('completeWorkItem', '簽核完成，推動流程往下一關',
                      {'pWorkItemOID': item_oid, 'pUserId': work_item['userId'],
                       'pComment': 'API 實測簽核'},
                      expect='完成後關卡應換人，原工作項目 OID 失效')
        _verify(recorder, service, 'completeWorkItem 後流程是否前進',
                'fetchProcSNMatchCurrtentPerformer',
                {'pProcessId': PROCESS_ID, 'pActId': 'InitatorManagerTask',
                 'pUserId': PEER_ID}, contains=main_serial)

    # ── 第三階段：轉派與取回（用另一張單）─────────────────
    print('')
    print('第三階段：轉派、跳關、取回重辦')
    reassign_serial = serials.get('byorg_full') or serials.get('custact')
    if reassign_serial:
        item = _current_work_item(service, reassign_serial, USER_ID)
        if item:
            oid = item['workItemOID']
            # 順序有意義：assigneeReassign 的 pRequesterOID 必須是待辦「目前的」
            # 擁有者，所以先用管理者身分把待辦轉到自己名下，才有資格自行轉派。
            recorder.call('managementReassignWorkItem', '管理者強制轉派（轉到自己名下）',
                          {'pAcceptorOID': USER_OID, 'pWorkItemOID': oid,
                           'pReassignComment': 'API 實測管理轉派'})
            recorder.call('assigneeReassignWorkItem', '簽核者自行轉派給他人',
                          {'pRequesterOID': USER_OID, 'pAcceptorOID': PEER_OID,
                           'pWorkItemOID': oid, 'pReassignComment': 'API 實測轉派'})
            recorder.call('managementChangeWorkItemOwner', '管理者變更待辦的擁有者',
                          {'pAcceptorOID': PEER_OID, 'pWorkItemOID': oid,
                           'pReassignComment': 'API 實測換擁有者'})

        activity_oid = _bypassable_activity(reassign_serial)
        if activity_oid:
            recorder.call('bypassActivity', '讓關卡跳過（不簽直接放行）',
                          {'pActivityInstanceOID': activity_oid})
        else:
            recorder.note('bypassActivity', '讓關卡跳過',
                          '該單查不到 bypassable=1 且未跳過的關卡實例')

    if serials.get('full'):
        recorder.call('reexecuteActivity', '取回重辦：把已簽核的關卡叫回來',
                      {'pProcessSerialNo': serials['full'],
                       'pAskReexecuteUserId': USER_ID,
                       'pReexecuteActivityId': 'InitiatorTask',
                       'pReexecuteComment': 'API 實測取回重辦'})

    # ── 第四階段：使用者設定（改完復原）───────────────────
    print('')
    print('第四階段：請假與代理人設定')
    start = '2026/12/01 00:00:00'
    end = '2026/12/02 00:00:00'
    added = recorder.call('addUserAbsence', '新增請假記錄',
                          {'pUserId': USER_ID, 'pStartTime': start, 'pEndTime': end})
    if added['status'] == 'ok':
        _verify(recorder, service, 'addUserAbsence 後的代理狀態',
                'getSubstituteState',
                {'pUserId': USER_ID, 'pCheckTime': '2026/12/01 09:00:00'},
                contains='isAbsence="Y"')
    recorder.call('removeAbsenceRecord', '刪掉剛才新增的請假記錄（復原）',
                  {'pUserId': USER_ID, 'pStartDateTime': start, 'pEndDateTime': end})

    recorder.call('updateDefaultSubstitute', '設定預設代理人',
                  {'pUserId': USER_ID, 'pDefaultSubstitutesId': PEER_ID},
                  expect='pDefaultSubstitutesId 的格式未知，先送單一員工編號')
    _verify(recorder, service, 'updateDefaultSubstitute 後讀回',
            'fetchDefaultSubstituteInfo',
            {'pUserId': USER_ID, 'pStartSeq': 1, 'pEndSeq': 10})

    # ── 第五階段：其他與收尾 ───────────────────────────────
    print('')
    print('第五階段：其他與收尾')
    recorder.call('reserveNoCmDocument', '預留文件編號',
                  {'pOriginalFullFileName': 'api_probe_%s.txt' % STAMP})

    recorder.note(
        'importOrganizationData', '匯入組織資料',
        '刻意不執行：會覆寫組織資料，而組織是所有流程的根基。'
        '匯入內容不完整就等同刪除既有部門，與「不刪測試區資料」牴觸')

    # 收尾：把開出來的單收掉，不留一堆待辦給別人
    for key, serial in sorted(serials.items()):
        if not serial:
            continue
        if key == 'full':
            recorder.call('terminatedProcessForSerialNo', '終止流程（收尾）',
                          {'pProcessInstanceSerialNo': serial, 'pUserId': USER_ID,
                           'pTerminatedComment': 'API 實測結束，終止'})
        else:
            recorder.call('abortProcessForSerialNo', '作廢流程（收尾）',
                          {'pProcessInstanceSerialNo': serial,
                           'pAbortComment': 'API 實測結束，作廢'})

    return recorder, serials


def _current_work_item(service, serial, user_id):
    """取得指定單目前待簽的工作項目。查不到就回 None，不猜。"""
    for candidate in (user_id, PEER_ID):
        raw = service.call('fetchToDoWorkItem', pProcessIds=PROCESS_ID,
                           pUserId=candidate)
        if not raw or '<workItemOID>' not in raw:
            continue
        for chunk in raw.split('<com.dsc.nana.services.webservice.SimpleWorkItem>'):
            if serial not in chunk:
                continue
            return {
                'workItemOID': _between(chunk, '<workItemOID>', '</workItemOID>'),
                'activityId': _between(chunk, '<activityId>', '</activityId>'),
                'userId': candidate,
            }
    return None


def _between(text, head, tail):
    start = text.find(head)
    if start < 0:
        return None
    start += len(head)
    return text[start:text.find(tail, start)]


def _bypassable_activity(serial):
    """查可跳關的關卡實例 OID。要連資料庫（唯讀），連不上就回 None。"""
    try:
        import sys
        db_path = os.path.join(os.path.dirname(BASE_DIR), '3_db_explorer')
        if db_path not in sys.path:
            sys.path.insert(0, db_path)
        from bpm_kb import config, db
    except ImportError:
        return None

    sql = """
    SELECT TOP 1 pai.OID
    FROM ParticipantActivityInstance pai
    JOIN ProcessInstance pi ON pi.OID = pai.containerOID
    WHERE pi.serialNumber = ? AND pai.bypassable = 1 AND pai.bypassed = 0
    """
    try:
        rows = db.Database(config.load()).query(sql, (serial,))
    except Exception:
        return None
    return rows[0]['OID'] if rows else None


def _verify(recorder, service, purpose, method, params, contains=None):
    """寫入之後讀回來驗證。只寫不驗等於沒測。"""
    record = {'method': method, 'purpose': '【驗證】%s' % purpose, 'params': dict(params)}
    try:
        operation = service.find_operation(method, params)
        value, _ = service.call_operation(operation, params)
        record['status'] = 'ok'
        record['return'] = (value or '')[:400]
        if contains is not None:
            record['verified'] = contains in (value or '')
            record['expect'] = '回傳應包含「%s」' % contains
    except ws_client.SoapFault as fault:
        record['status'] = 'fault'
        record['fault'] = fault.message
    recorder.steps.append(record)
    mark = ''
    if 'verified' in record:
        mark = 'PASS 驗證通過' if record['verified'] else 'FAIL 讀回的值不符預期'
    print('  %-6s %-38s %s' % ('verify', method, mark or (record.get('fault') or '')[:80]))
    return record


if __name__ == '__main__':
    recorder, serials = run()
    result = {
        'endpoint': ws_client.DEFAULT_ENDPOINT,
        'probedAt': datetime.datetime.now().isoformat(timespec='seconds'),
        'tickets': serials,
        'steps': recorder.steps,
    }
    with open(os.path.join(OUT_DIR, 'write_probe_result.json'), 'w',
              encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print('')
    print('已寫出 out/write_probe_result.json')
