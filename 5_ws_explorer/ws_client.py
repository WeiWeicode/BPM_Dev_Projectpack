# -*- coding: utf-8 -*-
"""呼叫 BPM WorkflowService 的極簡 SOAP 客戶端。

**為什麼手刻而不用套件**：這服務是 Apache Axis 1.3 的 `rpc`/`encoded`，
Python 的 zeep 明確不支援 SOAP encoding，suds 也已無人維護。
65 支方法的 envelope 格式完全一樣，手刻反而最短、最可控，
且符合本專案「不引入用不到的相依」的原則。

參數順序與型別直接讀 `out/WorkflowServiceService.json`（wsdl_dump.py 的產出），
呼叫端只要給 dict，順序與 xsi:type 由這裡依 parameterOrder 補齊 ——
rpc/encoded 是位置參數，順序錯了不會報錯，只會拿到錯的結果。

回傳值原樣送出（多為 XStream 序列化的 Java 物件 XML 字串），不在這裡解析。
SOAP Fault 一律拋 SoapFault，不吞錯、不回傳空值假裝成功。
"""

import json
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

API_PATH = os.path.join(BASE_DIR, 'out', 'WorkflowServiceService.json')

# 測試區。190 正式區在本工具中一律不連。
DEFAULT_ENDPOINT = 'http://10.10.130.191:8080/NaNaWeb/services/WorkflowService'

TIMEOUT = 60

SOAPENV = 'http://schemas.xmlsoap.org/soap/envelope/'

ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    '<soapenv:Body soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
    '<ns1:%s xmlns:ns1="%s">%s</ns1:%s>'
    '</soapenv:Body></soapenv:Envelope>'
)


class SoapFault(Exception):
    """SOAP Fault。message 為 faultstring，detail 保留原始回應供追查。"""

    def __init__(self, code, message, detail):
        Exception.__init__(self, '%s: %s' % (code, message))
        self.code = code
        self.message = message
        self.detail = detail


def _format_value(value, xsd_type):
    """依 WSDL 宣告的型別轉成 XML 文字。boolean 要小寫，Java 端不吃 True。"""
    if value is None:
        return ''
    if xsd_type == 'boolean':
        if isinstance(value, bool):
            return 'true' if value else 'false'
        return str(value).strip().lower()
    if xsd_type == 'int':
        return str(int(value))
    return escape(str(value))


class WorkflowService(object):
    """一個實例對應一台主機。無狀態，可重複呼叫。"""

    def __init__(self, endpoint=None, api_path=None):
        self.endpoint = endpoint or DEFAULT_ENDPOINT
        with open(api_path or API_PATH, 'r', encoding='utf-8') as handle:
            api = json.load(handle)
        self.namespace = api['targetNamespace']
        self.operations = api['operations']

    def find_operation(self, method, params=None):
        """挑出方法定義。同名多載靠參數名稱集合判斷，判不出來就要求指明。"""
        candidates = [item for item in self.operations if item['name'] == method]
        if not candidates:
            raise KeyError('WSDL 中沒有方法 %s' % method)
        if len(candidates) == 1:
            return candidates[0]

        keys = set(params or {})
        matched = [item for item in candidates
                   if set(part['name'] for part in item['parameters']) == keys]
        if len(matched) == 1:
            return matched[0]
        signatures = ' / '.join(
            '%s(%s)' % (item['inputMessage'],
                        ', '.join(part['name'] for part in item['parameters']))
            for item in candidates)
        raise KeyError('%s 有多載，參數無法唯一對應，請改用 call_operation()：%s'
                       % (method, signatures))

    def build_envelope(self, operation, params):
        """依 parameterOrder 組 body。缺少的參數以空值送出（Axis 視為 null）。"""
        unknown = set(params) - set(part['name'] for part in operation['parameters'])
        if unknown:
            raise KeyError('%s 沒有這些參數：%s' % (operation['name'], sorted(unknown)))

        parts = []
        for part in operation['parameters']:
            text = _format_value(params.get(part['name']), part['type'])
            parts.append('<%s xsi:type="xsd:%s">%s</%s>'
                         % (part['name'], part['type'], text, part['name']))
        return ENVELOPE % (operation['name'], self.namespace,
                           ''.join(parts), operation['name'])

    def call_operation(self, operation, params):
        """已知方法定義時的呼叫入口。回傳 (回傳值, 原始回應)。"""
        envelope = self.build_envelope(operation, params)
        request = urllib.request.Request(
            self.endpoint,
            data=envelope.encode('utf-8'),
            headers={
                'Content-Type': 'text/xml; charset=utf-8',
                # 這服務的 soapAction 全為空字串，分派靠 body 內的方法名
                'SOAPAction': '""',
            })
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                text = response.read().decode('utf-8')
        except urllib.error.HTTPError as error:
            # Axis 的 Fault 走 HTTP 500，內容才是有用的錯誤訊息
            text = error.read().decode('utf-8')
            raise _to_fault(text)
        return _unwrap(text, operation), text

    def call(self, method, **params):
        """一般用法：service.call('findFormOIDsOfProcess', pProcessPackageId='X')。"""
        operation = self.find_operation(method, params)
        value, _ = self.call_operation(operation, params)
        return value


def _to_fault(text):
    """把 Fault 回應轉成例外。解析不出來就把原文帶著，不要讓錯誤消失。"""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return SoapFault('ParseError', text[:200], text)
    fault = root.find('.//{%s}Fault' % SOAPENV)
    if fault is None:
        return SoapFault('HTTPError', text[:200], text)
    code = fault.findtext('faultcode') or ''
    message = fault.findtext('faultstring') or ''
    return SoapFault(code, message, text)


def _unwrap(text, operation):
    """取出 <方法名Return> 的文字。void 方法沒有這個元素，回傳 None。"""
    root = ET.fromstring(text)
    fault = root.find('.//{%s}Fault' % SOAPENV)
    if fault is not None:
        raise _to_fault(text)

    if not operation['returns']:
        return None
    name = operation['returns'][0]['name']
    for element in root.iter():
        if element.tag.split('}')[-1] == name:
            return element.text
    return None


if __name__ == '__main__':
    # 冒煙測試：用 bpmbackXmlController.js 已驗證過的兩支方法對答案
    service = WorkflowService()
    print(service.call('findFormOIDsOfProcess',
                       pProcessPackageId='Companycars_Application_solar_'))
    print(service.call('fetchOrgUnitOfUserId', pUserId='S112009')[:200])
