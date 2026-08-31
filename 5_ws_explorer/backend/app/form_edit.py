# -*- coding: utf-8 -*-
"""改單流程：查單 → 帶出欄位 → 編輯 → 寫回 → 讀回驗證。

**為什麼要獨立成一套，而不是靠通用實測工作台**：
updateFormValueBySerialNember 是「整份覆寫」，不是「合併」。實測結果：

    送出完整 15 欄、只改其中 2 欄 → 讀回 15 欄，只有那 2 欄變（正確）
    只送 1 欄                     → 讀回剩 1 欄，其餘 14 欄整個消失

而且它完全不驗證欄位 id 與 XML 結構。實測踩過一次：把
fetchFormInstanceWithProcSerlNo 的整包回傳（FormCollection）當成 pFormValue
貼回去，BPM 原樣收下，表單第一層變成 FormCollection 而非表單 id，
畫面上所有欄位就退回預設值 —— 看起來像資料被清空，其實只是多包了一層。

所以這裡把 XML 組裝整個收進後端：前端只送「哪個欄位改成什麼」。
後端在寫入前重新讀一次現值（不信任前端手上的舊快照）、只替換目標欄位的
內文、把整份送回去，再讀回來逐欄比對。任何一欄對不上就回報失敗，
不會因為 SOAP 沒丟例外就當作成功 —— 這支方法回傳 void，不讀回等於沒驗證。
"""

import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

import ws_client
from . import settings

# fetchProcInstances 的時間參數格式（Java SimpleDateFormat），與回傳的
# createdTime（yyyy-MM-dd HH:mm:ss.S，橫線）不同，不要混用。
WIDE_START = '2000/01/01 00:00:00'
WIDE_END = '2099/12/31 23:59:59'

# 被誤存成 pFormValue 的包裝層。第一層標籤是這些就代表單子被包壞了。
WRAPPER_TAGS = ('com.dsc.nana.services.webservice.FormCollection',
                'com.dsc.nana.services.webservice.FormInfo',
                'SimpleProcesses')

# 這些型別的欄位除了內文，還把顯示值放在屬性裡（label 顯示姓名、
# hidden 存 OID）。只改內文畫面不會同步，必須提醒。
ATTR_BACKED_TYPES = ('DIALOGINPUTLABEL', 'DIALOGINPUT', 'DIALOGINPUTMULTI')


class FormEditError(Exception):
    """改單流程的預期內錯誤，由路由層轉成 400。"""


def _client(endpoint: Optional[str] = None) -> ws_client.WorkflowService:
    """建立 SOAP 客戶端。190 正式區在這裡就擋掉，不留到呼叫時才發現。"""
    target = endpoint or settings.DEFAULT_ENDPOINT
    if '10.10.130.190' in target:
        raise FormEditError('190 正式區永久禁止連線（AGENTS.md 規則 8.1）')
    return ws_client.WorkflowService(endpoint=target,
                                     api_path=settings.API_JSON_PATH)


# ── 表單 XML 的讀與寫 ────────────────────────────────────────────

def unwrap_field_values(raw: str) -> Tuple[str, Optional[str]]:
    """從 fetchFormInstance* 的回傳剝出表單 XML。

    回傳 (表單XML, 異常說明)。異常說明不為 None 時代表這張單的 fieldValues
    被存成了包裝物件而非表單本體 —— 也就是曾經有人把整包回傳寫回去。
    這種情況下仍會把裡層的表單挖出來，讓使用者能一鍵修復。
    """
    field_values = ET.fromstring(raw).findtext('.//fieldValues')
    if not field_values or not field_values.strip():
        raise FormEditError('這張單沒有表單欄位值，可能是流程未掛表單。')

    text = field_values.strip()
    depth = 0
    while ET.fromstring(text).tag in WRAPPER_TAGS:
        inner = ET.fromstring(text).findtext('.//fieldValues')
        if not inner or not inner.strip():
            raise FormEditError('表單值被包在 %s 內且挖不出內層表單。'
                                % ET.fromstring(text).tag)
        text = inner.strip()
        depth += 1

    if depth:
        return text, (
            '這張單的表單值被多包了 %d 層 FormCollection —— 這是把 '
            'fetchFormInstance* 的整包回傳當成 pFormValue 寫回去造成的，'
            '畫面上會看到所有欄位退回預設值。下方顯示的是挖出來的真實內容，'
            '直接送出即可修復。' % depth)
    return text, None


def parse_form_xml(form_xml: str) -> Tuple[str, List[Dict[str, Any]]]:
    """把表單 XML 拆成 (表單id, 欄位清單)，保留原始順序與屬性。

    值以 ET 解析（已解逸出），寫回時再逸出。標籤重複時直接拋錯 ——
    字串定位法只會命中第一個，猜錯欄位比改不了更糟。
    """
    root = ET.fromstring(form_xml)
    seen: Dict[str, int] = {}
    fields: List[Dict[str, Any]] = []
    for element in root:
        seen[element.tag] = seen.get(element.tag, 0) + 1
        fields.append({
            'tag': element.tag,
            'id': element.get('id') or element.tag,
            'value': element.text if element.text is not None else '',
            'dataType': element.get('dataType'),
            'attributes': dict(element.attrib),
        })
    duplicated = sorted(tag for tag, count in seen.items() if count > 1)
    if duplicated:
        raise FormEditError('表單有重複的欄位標籤 %s，本工具無法安全定位，'
                            '請改用通用實測工作台手動處理。' % ', '.join(duplicated))
    return root.tag, fields


def set_field_value(form_xml: str, tag: str, value: str) -> str:
    """只替換單一欄位的內文，屬性與其餘位元組原樣保留。

    刻意不建 DOM 再序列化：BPM 的表單 XML 帶有屬性順序與空白慣例，
    重新序列化雖然仍是合法 XML，但沒必要冒這個險（同 1_xml_tool 的理由）。
    """
    head = form_xml.find('<%s ' % tag)
    if head < 0:
        head = form_xml.find('<%s>' % tag)
    if head < 0:
        raise FormEditError('表單沒有欄位 %s' % tag)
    start = form_xml.index('>', head) + 1
    end = form_xml.index('</%s>' % tag, start)
    return form_xml[:start] + escape(value) + form_xml[end:]


# ── 欄位中文名稱（唯讀資料庫，取不到就降級）──────────────────────

class LabelIndex(object):
    """把欄位 id 對成中文名稱與型別，資料來自 3_db_explorer 的 bpm_kb。

    這是選配的：沒有 .env、沒有 pyodbc、或資料庫連不上時，
    改單頁照常運作，只是名稱欄留白並在 API 回應帶上 labelSource 說明原因。
    不假裝查得到，也不因此讓整頁掛掉。
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Dict[str, str]]] = {}
        self._unavailable: Optional[str] = None

    def _extract(self):
        """延後 import：bpm_kb 會拉進 pyodbc 與 .env，不該在啟動時就要求。"""
        if settings.DB_EXPLORER_DIR not in sys.path:
            sys.path.insert(0, settings.DB_EXPLORER_DIR)
        from bpm_kb import db, extract  # noqa: E402
        return db, extract

    def labels_for(self, form_id: str) -> Tuple[Dict[str, Dict[str, str]], str]:
        """回傳 ({欄位id: {name, type}}, 來源說明)。查不到時第一項為空 dict。"""
        if not form_id:
            return {}, '未知表單 id，無法查名稱'
        if form_id in self._cache:
            return self._cache[form_id], '3_db_explorer/bpm_kb（唯讀資料庫）'
        if self._unavailable:
            return {}, self._unavailable

        try:
            db, extract = self._extract()
            with db.Database() as database:
                index = extract.form_index(database, [form_id])
        except ImportError as err:
            self._unavailable = '未安裝 bpm_kb 的相依套件（%s），只顯示欄位 id' % err
            return {}, self._unavailable
        except Exception as err:
            # 連不上資料庫不該讓改單頁失效，但也不能不說
            self._unavailable = '無法連線唯讀資料庫（%s: %s），只顯示欄位 id' % (
                type(err).__name__, str(err)[:120])
            return {}, self._unavailable

        self._cache[form_id] = index.get(form_id, {})
        if not self._cache[form_id]:
            return {}, '唯讀資料庫查得到連線，但沒有表單 %s 的定義' % form_id
        return self._cache[form_id], '3_db_explorer/bpm_kb（唯讀資料庫）'


label_index = LabelIndex()


# ── 流程清單 ────────────────────────────────────────────────────

def list_processes(keyword: str = '', limit: int = 200) -> Dict[str, Any]:
    """流程清單，來源是 3_db_explorer/out/form_process_map.json。

    WorkflowService 沒有「列出所有流程」的方法（fetchProcInstances 一定要先
    給 pProcessId），所以流程 id 只能從別處來。這份檔案是
    form_process_map.py 的產出，含中文流程名與掛的表單，不重寫查詢（AGENTS.md 7.5）。
    檔案不在時回傳空清單並說明原因，使用者仍可直接輸入流程 id 或單號。
    """
    path = settings.FORM_PROCESS_MAP_PATH
    if not os.path.exists(path):
        return {
            'processes': [], 'total': 0, 'truncated': False,
            'source': '找不到 %s，請先執行 3_db_explorer/form_process_map.py；'
                      '仍可直接輸入流程 id 或單號查詢' % path,
        }

    with open(path, 'r', encoding='utf-8') as handle:
        rows = json.load(handle)

    needle = (keyword or '').strip().lower()
    matched = []
    for row in rows:
        forms = row.get('forms') or []
        haystack = ' '.join([
            row.get('processId') or '', row.get('processName') or '',
            ' '.join((f.get('formId') or '') + ' ' + (f.get('formName') or '')
                     for f in forms),
        ]).lower()
        if needle and needle not in haystack:
            continue
        matched.append({
            'processId': row.get('processId'),
            'processName': row.get('processName'),
            'version': row.get('version'),
            'formIds': [f.get('formId') for f in forms if f.get('formId')],
            'formNames': [f.get('formName') for f in forms if f.get('formName')],
        })

    matched.sort(key=lambda r: (r['processId'] or '').lower())
    return {
        'processes': matched[:limit],
        'total': len(matched),
        'truncated': len(matched) > limit,
        'source': 'form_process_map.json（%d 支流程）' % len(rows),
    }


def list_instances(process_id: str, scope: str = 'all',
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None,
                   date_basis: str = 'created',
                   endpoint: Optional[str] = None) -> Dict[str, Any]:
    """查某支流程的單，涵蓋進行中與已結案。

    date_basis='created' 走 fetchProcInstances（比對建立時間），
    'closed' 走 fetchClosedProcInstances（比對結案時間）—— 兩者時間語意不同，
    問「上個月結案的單」時只有後者答得對。

    scope 的過濾在這裡做而不是丟給 pProcInstanceState：實測該參數只吃
    完整值（'open' 會被拒），而 closed 有 completed / terminated 等多種，
    列舉不全會靜默漏單。取全部再依前綴篩，漏不掉。
    """
    if not process_id:
        raise FormEditError('請先指定流程 id')

    service = _client(endpoint)
    started = time.time()
    if date_basis == 'closed':
        raw = service.call('fetchClosedProcInstances',
                           pProcessId=process_id,
                           pProcessClosedStartTime=start_time or WIDE_START,
                           pProcessClosedEndTime=end_time or WIDE_END,
                           pProcInstanceClosedState='')
        used = 'fetchClosedProcInstances（依結案時間）'
    else:
        raw = service.call('fetchProcInstances',
                           pProcessId=process_id,
                           pProcessInitialStartTime=start_time or WIDE_START,
                           pProcessInitialEndTime=end_time or WIDE_END,
                           pProcInstanceState='')
        used = 'fetchProcInstances（依建立時間）'

    instances = []
    for element in ET.fromstring(raw):
        state = element.findtext('state') or ''
        if scope == 'running' and not state.startswith('open.'):
            continue
        if scope == 'closed' and not state.startswith('closed.'):
            continue
        instances.append({
            'serialNo': element.findtext('serialNo'),
            'oid': element.findtext('OID'),
            'state': state,
            'subject': element.findtext('subject'),
            'requesterId': element.findtext('requesterId'),
            'requesterName': element.findtext('requesterName'),
            'createdTime': element.findtext('createdTime'),
            'processId': element.findtext('processId'),
            'processName': element.findtext('processName'),
        })
    return {
        'instances': instances,
        'total': len(instances),
        'method': used,
        'elapsedMs': int((time.time() - started) * 1000),
    }


# ── 讀單與寫回 ──────────────────────────────────────────────────

def load_instance(serial_no: str,
                  endpoint: Optional[str] = None) -> Dict[str, Any]:
    """載入一張單的單頭與可編輯欄位表。"""
    if not serial_no or not serial_no.strip():
        raise FormEditError('請輸入單號')
    serial_no = serial_no.strip()

    service = _client(endpoint)
    started = time.time()

    try:
        header_raw = service.call('fetchProcInstanceWithSerialNo',
                                  pProcessInstanceSerialNo=serial_no)
    except ws_client.SoapFault as fault:
        raise FormEditError('查不到單號 %s：%s' % (serial_no, fault.message))

    header_root = ET.fromstring(header_raw)
    header = {
        'serialNo': header_root.findtext('serialNo'),
        'oid': header_root.findtext('OID'),
        'state': header_root.findtext('state'),
        'subject': header_root.findtext('subject'),
        'requesterId': header_root.findtext('requesterId'),
        'requesterName': header_root.findtext('requesterName'),
        'createdTime': header_root.findtext('createdTime'),
        'processId': header_root.findtext('processId'),
        'processName': header_root.findtext('processName'),
    }

    form_raw = service.call('fetchFormInstanceWithProcSerlNo',
                            pProcessInstanceSerialNo=serial_no)
    form_id_outer = ET.fromstring(form_raw).findtext('.//formId')
    form_xml, corruption = unwrap_field_values(form_raw)
    form_id, fields = parse_form_xml(form_xml)

    labels, label_source = label_index.labels_for(form_id)
    for field in fields:
        meta = labels.get(field['id']) or {}
        field['name'] = meta.get('name')
        field['fieldType'] = meta.get('type')
        field['attrBacked'] = meta.get('type') in ATTR_BACKED_TYPES
        # 這些屬性是欄位本身的設定，不是資料；列出來讓人知道改內文改不到它們
        field['extraAttributes'] = dict(
            (k, v) for k, v in field['attributes'].items()
            if k not in ('id', 'dataType'))

    return {
        'header': header,
        'formId': form_id,
        'formIdFromResponse': form_id_outer,
        'formSerialNumber': ET.fromstring(form_raw).findtext('.//serialNumber'),
        'fields': fields,
        'rawFormXml': form_xml,
        'labelSource': label_source,
        'labelsAvailable': bool(labels),
        'corruption': corruption,
        'closed': (header.get('state') or '').startswith('closed.'),
        'elapsedMs': int((time.time() - started) * 1000),
    }


def preview_changes(serial_no: str, changes: Dict[str, str],
                    endpoint: Optional[str] = None) -> Dict[str, Any]:
    """算出「會送出什麼」而不真的送。給前端在按下確認前對照用。"""
    current = load_instance(serial_no, endpoint)
    form_xml = current['rawFormXml']
    before = dict((f['tag'], f['value']) for f in current['fields'])

    diff = []
    for tag, value in (changes or {}).items():
        if tag not in before:
            raise FormEditError('表單沒有欄位 %s' % tag)
        if before[tag] == value:
            continue
        form_xml = set_field_value(form_xml, tag, value)
        diff.append({'tag': tag, 'before': before[tag], 'after': value})

    return {
        'serialNo': current['header']['serialNo'],
        'diff': diff,
        'fieldCount': len(current['fields']),
        'pFormValue': form_xml,
        'unchanged': not diff and not current.get('corruption'),
    }


def submit_changes(serial_no: str,
                   changes: Optional[Dict[str, str]] = None,
                   raw_form_xml: Optional[str] = None,
                   confirm: bool = False,
                   endpoint: Optional[str] = None) -> Dict[str, Any]:
    """寫回表單值，然後讀回逐欄比對。

    confirm 是硬性的：這支方法整份覆寫且沒有復原機制，
    不讓前端漏傳旗標就把單子蓋掉（同工作台對 write 方法的規矩）。

    raw_form_xml 供「還原」用：把先前備份的整份 XML 原樣送回。
    一般編輯請走 changes，由後端在寫入前重讀現值再套用，避免蓋掉
    這段期間別人改的欄位。
    """
    if not confirm:
        raise FormEditError('updateFormValueBySerialNember 會整份覆寫表單值且無法復原，'
                            '必須確認後才能送出。')
    # 這裡刻意不擋「沒有 changes」：修復結構異常的單就是不改任何欄位、
    # 只把剝好的表單重新寫回去。真正沒事可做的情況由下方的 unchanged 分支處理。

    service = _client(endpoint)
    started = time.time()

    current = load_instance(serial_no, endpoint)
    serial_no = current['header']['serialNo']
    backup_xml = current['rawFormXml']

    if raw_form_xml:
        payload = raw_form_xml
        expected = dict((f['tag'], f['value'])
                        for f in parse_form_xml(payload)[1])
        diff = []
    else:
        payload = backup_xml
        before = dict((f['tag'], f['value']) for f in current['fields'])
        diff = []
        for tag, value in (changes or {}).items():
            if tag not in before:
                raise FormEditError('表單沒有欄位 %s' % tag)
            if before[tag] == value:
                continue
            payload = set_field_value(payload, tag, value)
            diff.append({'tag': tag, 'before': before[tag], 'after': value})
        expected = dict((tag, value) for tag, value in (changes or {}).items()
                        if tag in before)
        if not diff and not current.get('corruption'):
            return {
                'status': 'unchanged', 'serialNo': serial_no, 'diff': [],
                'verified': True, 'mismatches': [], 'backupFormXml': backup_xml,
                'pFormValue': payload, 'fieldCountAfter': len(current['fields']),
                'elapsedMs': int((time.time() - started) * 1000),
                'message': '沒有任何欄位變更，未送出。',
            }

    try:
        service.call('updateFormValueBySerialNember',
                     serialNumber=serial_no, pFormValue=payload)
    except ws_client.SoapFault as fault:
        raise FormEditError('寫入失敗：%s' % fault.message)

    # 這支回 void，不讀回等於沒驗證
    after = load_instance(serial_no, endpoint)
    after_values = dict((f['tag'], f['value']) for f in after['fields'])
    mismatches = [
        {'tag': tag, 'expected': value, 'actual': after_values.get(tag)}
        for tag, value in expected.items()
        if after_values.get(tag) != value
    ]

    return {
        'status': 'ok' if not mismatches else 'mismatch',
        'serialNo': serial_no,
        'diff': diff,
        'verified': not mismatches,
        'mismatches': mismatches,
        'backupFormXml': backup_xml,
        'pFormValue': payload,
        'fieldCountBefore': len(current['fields']),
        'fieldCountAfter': len(after['fields']),
        'corruptionCleared': bool(current.get('corruption')) and not after.get('corruption'),
        'elapsedMs': int((time.time() - started) * 1000),
        'message': ('已寫入並讀回驗證通過。' if not mismatches else
                    '已寫入，但讀回比對有 %d 欄對不上，請檢查。' % len(mismatches)),
    }
