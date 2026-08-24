# -*- coding: utf-8 -*-
"""抓取 BPM SOAP 服務的 WSDL，擷取「有哪些方法、各吃什麼參數」。

本階段只做「紀錄」：把 WSDL 裡的介面契約攤平成 JSON 與 Markdown，
不判斷用途、不推測語意、不產生呼叫程式碼。

鼎新 NaNaWeb 的 WorkflowService 由 Apache Axis 1.3 產生，特徵是：

  * style="rpc" / use="encoded" —— 舊式 SOAP，不是 document/literal。
    參數順序有意義，靠 parameterOrder 決定，不能只看 message 的宣告順序。
  * soapAction 全為空字串 —— 分派靠 body 內的方法名，不是 HTTP 標頭。
  * 沒有 <wsdl:types> 區塊 —— 全部是 xsd 內建型別（string/int/boolean），
    因此不需要處理 complexType 或 schema import。

解析用 ElementTree 即可：這裡是唯讀擷取，沒有回寫需求，
與 1_xml_tool「位元組級無損」的限制無關。

產出（預設 out/）：
    WorkflowServiceService.wsdl   原始 WSDL，保留現場
    WorkflowServiceService.json   結構化的方法與參數清單
    WorkflowServiceService.md     人看的對照表

用法：
    python wsdl_dump.py                     # 抓預設測試區位址
    python wsdl_dump.py <wsdl 網址>
    python wsdl_dump.py --file <本機 wsdl>  # 離線解析已抓下來的檔案
"""

import datetime
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_URL = 'http://10.10.130.191:8080/NaNaWeb/services/WorkflowService?wsdl'

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')

TIMEOUT = 30

NS = {
    'wsdl': 'http://schemas.xmlsoap.org/wsdl/',
    'soap': 'http://schemas.xmlsoap.org/wsdl/soap/',
    'xsd': 'http://www.w3.org/2001/XMLSchema',
}


def _local(name):
    """去掉 QName 前綴，只留本地名稱（impl:fooRequest → fooRequest）。"""
    if name is None:
        return None
    return name.split(':')[-1]


def fetch(url):
    """抓 WSDL 原文。抓不到就讓例外往上拋，不吞錯。"""
    request = urllib.request.Request(url, headers={'User-Agent': 'bpm-wsdl-dump/1.0'})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode('utf-8')


def _messages(root):
    """message 名稱 → [{name, type}]，順序即 WSDL 中的宣告順序。"""
    result = {}
    for message in root.findall('wsdl:message', NS):
        parts = []
        for part in message.findall('wsdl:part', NS):
            parts.append({
                'name': part.get('name'),
                'type': _local(part.get('type') or part.get('element')),
            })
        result[message.get('name')] = parts
    return result


def _soap_actions(root):
    """binding 裡的 soapAction，key 為操作名稱。Axis 產的通常全是空字串。"""
    result = {}
    for binding in root.findall('wsdl:binding', NS):
        for operation in binding.findall('wsdl:operation', NS):
            soap_operation = operation.find('soap:operation', NS)
            if soap_operation is not None:
                result[operation.get('name')] = soap_operation.get('soapAction') or ''
    return result


def _binding_style(root):
    """回傳 (style, use)。rpc/encoded 與 document/literal 的組包方式完全不同。"""
    style = None
    use = None
    for binding in root.findall('wsdl:binding', NS):
        soap_binding = binding.find('soap:binding', NS)
        if soap_binding is not None and style is None:
            style = soap_binding.get('style')
        for body in binding.iter('{%s}body' % NS['soap']):
            if use is None:
                use = body.get('use')
    return style, use


def _endpoint(root):
    """服務實際位址（?wsdl 之外的那個 endpoint）。"""
    for service in root.findall('wsdl:service', NS):
        for port in service.findall('wsdl:port', NS):
            address = port.find('soap:address', NS)
            if address is not None:
                return {
                    'service': service.get('name'),
                    'port': port.get('name'),
                    'location': address.get('location'),
                }
    return {'service': None, 'port': None, 'location': None}


def parse(xml_text, source):
    """把 WSDL 攤平成方法清單。"""
    root = ET.fromstring(xml_text)
    messages = _messages(root)
    actions = _soap_actions(root)
    style, use = _binding_style(root)

    operations = []
    for port_type in root.findall('wsdl:portType', NS):
        for operation in port_type.findall('wsdl:operation', NS):
            name = operation.get('name')
            order = (operation.get('parameterOrder') or '').split()

            input_element = operation.find('wsdl:input', NS)
            output_element = operation.find('wsdl:output', NS)
            input_message = _local(input_element.get('message')) if input_element is not None else None
            output_message = _local(output_element.get('message')) if output_element is not None else None

            parts = messages.get(input_message, [])
            # parameterOrder 才是呼叫時的實際順序，message 宣告順序不保證一致
            if order:
                by_name = dict((part['name'], part) for part in parts)
                ordered = [by_name[key] for key in order if key in by_name]
                ordered += [part for part in parts if part['name'] not in order]
                parts = ordered

            operations.append({
                'name': name,
                'portType': port_type.get('name'),
                'soapAction': actions.get(name, ''),
                'parameterOrder': order,
                'parameters': parts,
                'returns': messages.get(output_message, []),
                'inputMessage': input_message,
                'outputMessage': output_message,
            })

    operations.sort(key=lambda item: item['name'])

    result = _endpoint(root)
    result.update({
        'source': source,
        'fetchedAt': datetime.datetime.now().isoformat(timespec='seconds'),
        'targetNamespace': root.get('targetNamespace'),
        'style': style,
        'use': use,
        'operationCount': len(operations),
        'operations': operations,
    })
    return result


def _signature(operation):
    """組成 name(型別 參數, ...) : 回傳型別，方便一眼掃過。"""
    args = ', '.join('%s %s' % (part['type'], part['name']) for part in operation['parameters'])
    if operation['returns']:
        returns = ', '.join(part['type'] for part in operation['returns'])
    else:
        returns = 'void'
    return '%s(%s) : %s' % (operation['name'], args, returns)


def to_markdown(api):
    """輸出對照表。不加任何用途說明 —— 那是下一階段人工分析的事。"""
    lines = []
    lines.append('# %s API 清單' % (api['service'] or 'SOAP Service'))
    lines.append('')
    lines.append('> 由 `wsdl_dump.py` 自 WSDL 擷取，只記錄介面契約，未分析用途。')
    lines.append('')
    lines.append('| 項目 | 值 |')
    lines.append('|:---|:---|')
    lines.append('| WSDL | `%s` |' % api['source'])
    lines.append('| Endpoint | `%s` |' % api['location'])
    lines.append('| targetNamespace | `%s` |' % api['targetNamespace'])
    lines.append('| SOAP 風格 | `%s` / `%s` |' % (api['style'], api['use']))
    lines.append('| 方法數 | %d |' % api['operationCount'])
    lines.append('| 擷取時間 | %s |' % api['fetchedAt'])
    lines.append('')
    lines.append('## 方法一覽')
    lines.append('')
    lines.append('| # | 方法 | 參數（依 parameterOrder） | 回傳 |')
    lines.append('|---:|:---|:---|:---|')
    for index, operation in enumerate(api['operations'], 1):
        if operation['parameters']:
            args = '<br>'.join(
                '`%s` %s' % (part['name'], part['type']) for part in operation['parameters'])
        else:
            args = '（無）'
        if operation['returns']:
            returns = ', '.join(part['type'] for part in operation['returns'])
        else:
            returns = 'void'
        lines.append('| %d | `%s` | %s | `%s` |' % (index, operation['name'], args, returns))
    lines.append('')
    lines.append('## 簽章速查')
    lines.append('')
    lines.append('```')
    for operation in api['operations']:
        lines.append(_signature(operation))
    lines.append('```')
    lines.append('')
    return '\n'.join(lines)


def _write(path, text):
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    print('寫出 %s' % path)


def main(argv):
    source = DEFAULT_URL
    local_file = None
    args = argv[1:]
    if args and args[0] == '--file':
        if len(args) < 2:
            print('--file 後面要接檔案路徑')
            return 2
        local_file = args[1]
        source = local_file
    elif args:
        source = args[0]

    if local_file:
        with open(local_file, 'r', encoding='utf-8') as handle:
            xml_text = handle.read()
    else:
        print('抓取 %s' % source)
        xml_text = fetch(source)

    api = parse(xml_text, source)
    print('解析到 %d 個方法（%s/%s）' % (api['operationCount'], api['style'], api['use']))

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    name = api['service'] or 'service'
    if not local_file:
        _write(os.path.join(OUT_DIR, '%s.wsdl' % name), xml_text)
    _write(os.path.join(OUT_DIR, '%s.json' % name),
           json.dumps(api, ensure_ascii=False, indent=2))
    _write(os.path.join(OUT_DIR, '%s.md' % name), to_markdown(api))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
