# -*- coding: utf-8 -*-
"""資料載入、整合分析與 SOAP 呼叫服務。"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import ws_client
from . import settings
from .schemas import (
    InvokeResult,
    OperationDetail,
    OperationSummary,
    OverviewSummary,
    ParameterInfo,
    ReturnInfo,
    SeedsData,
)

CONFIDENCE_LABELS = {
    'verified': '✅ 已實測',
    'external': '☑️ 既有服務驗證',
    'guess': '⚠️ 僅推測',
    'none': '⚠️ 尚未分析',
}

STATUS_LABELS = {
    'ok': '實測成功',
    'fault': 'SOAP Fault',
    'error': '連線失敗',
    'soft_error': '假成功',
    'skipped': '未實測',
}

READ_VERBS = ('fetch', 'get', 'find', 'count', 'is', 'check')
SUSPECT = ('management',)


def classify_level(name: str) -> str:
    """判斷方法為唯讀 (read) 或有副作用 (write)。動詞未明確列舉者一律視為 write。"""
    match = re.match(r'[a-z]+', name)
    if not match:
        return 'write'
    verb = match.group()
    if verb in SUSPECT:
        return 'write'
    return 'read' if verb in READ_VERBS else 'write'


def extract_shape(text: Optional[str]) -> Optional[str]:
    """將回傳之 XML 壓成標籤階層輪廓。"""
    if not text:
        return None
    stripped = text.strip()
    if not stripped.startswith('<'):
        return '（非 XML 純值）'
    tags: List[str] = []
    for tag in re.findall(r'<([A-Za-z][\w.$]*)[\s>/]', stripped):
        if tag not in tags:
            tags.append(tag)
    return ' > '.join(tags[:12])


class WsExplorerService(object):
    """資料快取與 SOAP 呼叫管理。"""

    def __init__(self):
        self._api: Optional[Dict[str, Any]] = None
        self._probe: Optional[Dict[str, Any]] = None
        self._notes: Optional[Dict[str, Any]] = None
        self._seeds: Optional[Dict[str, Any]] = None
        self.reload()

    def reload(self):
        """重新載入檔案資料。"""
        if os.path.exists(settings.API_JSON_PATH):
            with open(settings.API_JSON_PATH, 'r', encoding='utf-8') as handle:
                self._api = json.load(handle)
        else:
            self._api = {'operations': [], 'targetNamespace': '', 'operationCount': 0}

        if os.path.exists(settings.PROBE_JSON_PATH):
            with open(settings.PROBE_JSON_PATH, 'r', encoding='utf-8') as handle:
                self._probe = json.load(handle)
        else:
            self._probe = {'results': [], 'summary': {}, 'endpoint': settings.DEFAULT_ENDPOINT}

        if os.path.exists(settings.NOTES_JSON_PATH):
            with open(settings.NOTES_JSON_PATH, 'r', encoding='utf-8') as handle:
                self._notes = json.load(handle)
        else:
            self._notes = {}

        if os.path.exists(settings.SEEDS_JSON_PATH):
            with open(settings.SEEDS_JSON_PATH, 'r', encoding='utf-8') as handle:
                self._seeds = json.load(handle)
        else:
            self._seeds = {}

    def _get_note(self, name: str) -> Optional[Dict[str, Any]]:
        if not self._notes:
            return None
        return self._notes.get(name)

    def _get_probe_record(self, input_message: str, name: str) -> Optional[Dict[str, Any]]:
        if not self._probe or 'results' not in self._probe:
            return None
        for item in self._probe['results']:
            if item.get('inputMessage') == input_message or item.get('name') == name:
                return item
        return None

    def _get_seed_value(self, op_name: str, param_name: str) -> Any:
        if not self._seeds:
            return None
        overrides = self._seeds.get('_overrides', {}).get(op_name, {})
        if param_name in overrides:
            return overrides[param_name]
        return self._seeds.get(param_name)

    def get_overview(self) -> OverviewSummary:
        operations = self._api.get('operations', []) if self._api else []
        notes = self._notes or {}
        documented = [op for op in operations if op['name'] in notes and not op['name'].startswith('_')]
        
        probe_results = self._probe.get('results', []) if self._probe else []
        verified_count = sum(1 for item in probe_results if item.get('status') == 'ok')

        status_counts: Dict[str, int] = {}
        for op in operations:
            probe_rec = self._get_probe_record(op.get('inputMessage', ''), op['name'])
            st = probe_rec.get('status', 'skipped') if probe_rec else 'skipped'
            status_counts[st] = status_counts.get(st, 0) + 1

        confidence_counts: Dict[str, int] = {}
        for op in operations:
            note = self._get_note(op['name'])
            conf = note.get('信心', 'none') if note else 'none'
            confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

        level_counts = {'read': 0, 'write': 0}
        for op in operations:
            lvl = classify_level(op['name'])
            level_counts[lvl] = level_counts.get(lvl, 0) + 1

        return OverviewSummary(
            endpoint=self._probe.get('endpoint', settings.DEFAULT_ENDPOINT) if self._probe else settings.DEFAULT_ENDPOINT,
            targetNamespace=self._api.get('targetNamespace', '') if self._api else '',
            operationCount=len(operations),
            documentedCount=len(documented),
            verifiedCount=verified_count,
            probedAt=self._probe.get('probedAt') if self._probe else None,
            statusCounts=status_counts,
            confidenceCounts=confidence_counts,
            levelCounts=level_counts,
        )

    def get_seeds(self) -> SeedsData:
        if not self._seeds:
            return SeedsData()
        sources = self._seeds.get('_來源', {})
        overrides = self._seeds.get('_overrides', {})
        shared = dict((k, v) for k, v in self._seeds.items() if not k.startswith('_'))
        return SeedsData(seeds=shared, sources=sources, overrides=overrides)

    def list_operations(
        self,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        confidence: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[OperationSummary]:
        if not self._api:
            return []

        kw = (keyword or '').strip().lower()
        items: List[OperationSummary] = []

        for op in self._api.get('operations', []):
            op_name = op['name']
            input_msg = op.get('inputMessage', op_name + 'Request')
            lvl = classify_level(op_name)
            note = self._get_note(op_name)
            probe_rec = self._get_probe_record(input_msg, op_name)

            conf_key = note.get('信心', 'none') if note else 'none'
            conf_label = CONFIDENCE_LABELS.get(conf_key, CONFIDENCE_LABELS['none'])

            st_key = probe_rec.get('status', 'skipped') if probe_rec else 'skipped'
            st_label = STATUS_LABELS.get(st_key, st_key)

            purpose = note.get('用途') if note else None
            param_descs = note.get('參數', {}) if note else {}

            params: List[ParameterInfo] = []
            for p in op.get('parameters', []):
                p_name = p['name']
                params.append(ParameterInfo(
                    name=p_name,
                    type=p.get('type', 'string'),
                    description=param_descs.get(p_name),
                    defaultValue=self._get_seed_value(op_name, p_name),
                ))

            ret_info = None
            if op.get('returns'):
                ret = op['returns'][0]
                ret_info = ReturnInfo(
                    type=ret.get('type', 'void'),
                    name=ret.get('name'),
                    description=note.get('回傳') if note else None,
                )

            payload_path = probe_rec.get('payload') if probe_rec else None
            has_payload = bool(payload_path and os.path.exists(os.path.join(settings.PROJECT_DIR, payload_path)))

            # 過濾條件
            if level and level != 'all' and lvl != level:
                continue
            if confidence and confidence != 'all' and conf_key != confidence:
                continue
            if status and status != 'all' and st_key != status:
                continue

            if kw:
                haystack = '%s %s %s %s' % (
                    op_name.lower(),
                    (purpose or '').lower(),
                    ' '.join(p.name.lower() for p in params),
                    (note.get('備註', '') if note else '').lower(),
                )
                if kw not in haystack:
                    continue

            items.append(OperationSummary(
                name=op_name,
                inputMessage=input_msg,
                level=lvl,
                confidence=conf_key,
                confidenceLabel=conf_label,
                status=st_key,
                statusLabel=st_label,
                elapsedMs=probe_rec.get('elapsedMs') if probe_rec else None,
                purpose=purpose,
                parameterCount=len(params),
                parameters=params,
                returns=ret_info,
                hasPayload=has_payload,
            ))

        return items

    def get_operation_detail(self, name: str, input_message: Optional[str] = None) -> Optional[OperationDetail]:
        if not self._api:
            return None

        matched_op = None
        for op in self._api.get('operations', []):
            if op['name'] == name:
                if input_message and op.get('inputMessage') != input_message:
                    continue
                matched_op = op
                break

        if not matched_op:
            return None

        op_name = matched_op['name']
        input_msg = matched_op.get('inputMessage', op_name + 'Request')
        lvl = classify_level(op_name)
        note = self._get_note(op_name)
        probe_rec = self._get_probe_record(input_msg, op_name)

        conf_key = note.get('信心', 'none') if note else 'none'
        conf_label = CONFIDENCE_LABELS.get(conf_key, CONFIDENCE_LABELS['none'])

        st_key = probe_rec.get('status', 'skipped') if probe_rec else 'skipped'
        st_label = STATUS_LABELS.get(st_key, st_key)

        param_descs = note.get('參數', {}) if note else {}
        params: List[ParameterInfo] = []
        for p in matched_op.get('parameters', []):
            p_name = p['name']
            params.append(ParameterInfo(
                name=p_name,
                type=p.get('type', 'string'),
                description=param_descs.get(p_name),
                defaultValue=self._get_seed_value(op_name, p_name),
            ))

        ret_info = None
        if matched_op.get('returns'):
            ret = matched_op['returns'][0]
            ret_info = ReturnInfo(
                type=ret.get('type', 'void'),
                name=ret.get('name'),
                description=note.get('回傳') if note else None,
            )

        payload_path = probe_rec.get('payload') if probe_rec else None
        payload_sample = None
        if payload_path:
            full_path = os.path.join(settings.PROJECT_DIR, payload_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as handle:
                        payload_sample = handle.read()
                except Exception:
                    payload_sample = None

        args_str = ', '.join('%s %s' % (p.type, p.name) for p in params)
        ret_type_str = ret_info.type if ret_info else 'void'
        signature = '%s(%s) : %s' % (op_name, args_str, ret_type_str)

        return OperationDetail(
            name=op_name,
            inputMessage=input_msg,
            portType=matched_op.get('portType', 'WorkflowService'),
            parameterOrder=matched_op.get('parameterOrder', []),
            level=lvl,
            confidence=conf_key,
            confidenceLabel=conf_label,
            status=st_key,
            statusLabel=st_label,
            elapsedMs=probe_rec.get('elapsedMs') if probe_rec else None,
            purpose=note.get('用途') if note else None,
            parameters=params,
            returns=ret_info,
            remarks=note.get('備註') if note else None,
            payloadPath=payload_path,
            payloadSample=payload_sample,
            faultCode=probe_rec.get('faultCode') if probe_rec else None,
            faultString=probe_rec.get('faultString') if probe_rec else None,
            error=probe_rec.get('error') if probe_rec else None,
            softError=probe_rec.get('softError') if probe_rec else None,
            reason=probe_rec.get('reason') if probe_rec else None,
            returnShape=probe_rec.get('returnShape') if probe_rec else None,
            signature=signature,
        )

    def get_payload(self, name: str) -> Optional[str]:
        """由檔名（或 inputMessage）取得 XML 樣本。"""
        fname = name if name.endswith('.xml') else '%s.xml' % name
        path = os.path.join(settings.PAYLOAD_DIR, fname)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()

    def invoke(
        self,
        operation_name: str,
        input_message: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        allow_write: bool = False,
        endpoint: Optional[str] = None,
    ) -> InvokeResult:
        """執行即時 SOAP 呼叫，嚴格檢查 190 邊界與寫入旗標。"""
        target_endpoint = endpoint or settings.DEFAULT_ENDPOINT
        if '10.10.130.190' in target_endpoint:
            return InvokeResult(
                status='error',
                elapsedMs=0,
                error='190 正式區永久禁止連線（AGENTS.md 規則 8.1）',
            )

        level = classify_level(operation_name)
        if level == 'write' and not allow_write:
            return InvokeResult(
                status='error',
                elapsedMs=0,
                error='此方法具有副作用（開單/簽核/轉派/作廢等），必須勾選「確認在測試區執行」後才能送出。',
            )

        service = ws_client.WorkflowService(endpoint=target_endpoint, api_path=settings.API_JSON_PATH)

        # 挑出正確的 operation
        candidates = [op for op in service.operations if op['name'] == operation_name]
        if not candidates:
            return InvokeResult(status='error', elapsedMs=0, error='找不到方法：%s' % operation_name)

        target_op = candidates[0]
        if len(candidates) > 1 and input_message:
            for op in candidates:
                if op.get('inputMessage') == input_message:
                    target_op = op
                    break

        sent_params = params or {}
        envelope = service.build_envelope(target_op, sent_params)

        started = time.time()
        try:
            value, raw = service.call_operation(target_op, sent_params)
            elapsed = int((time.time() - started) * 1000)

            # 檢查假成功（HTTP 200 包著例外字串）
            if value and value.lstrip().startswith('<') and 'Exception>' in value[:300]:
                return InvokeResult(
                    status='soft_error',
                    elapsedMs=elapsed,
                    value=value,
                    rawResponse=raw,
                    requestEnvelope=envelope,
                    returnShape=extract_shape(value),
                    softError=value.strip()[:500],
                )

            return InvokeResult(
                status='ok',
                elapsedMs=elapsed,
                value=value,
                rawResponse=raw,
                requestEnvelope=envelope,
                returnShape=extract_shape(value),
            )

        except ws_client.SoapFault as fault:
            elapsed = int((time.time() - started) * 1000)
            return InvokeResult(
                status='fault',
                elapsedMs=elapsed,
                faultCode=fault.code,
                faultString=fault.message,
                rawResponse=fault.detail,
                requestEnvelope=envelope,
            )
        except Exception as err:
            elapsed = int((time.time() - started) * 1000)
            return InvokeResult(
                status='error',
                elapsedMs=elapsed,
                error='%s: %s' % (type(err).__name__, err),
                requestEnvelope=envelope,
            )


service = WsExplorerService()
