# -*- coding: utf-8 -*-
"""解析 FormInstance.fieldValues —— 一張單的表單內容。

實測得出的結構（樣本：ITAccount_Application00001550）：

    <表單id>
      <欄位id id="欄位id" dataType="java.lang.String">值</欄位id>
      <Grid11 id="Grid11">
        <records>
          <record id="Grid11_0">
            <item id="G_s_Sys_Name" dataType="java.lang.String">值</item>
            ...

也就是「單頭欄位」與「表格明細」混在同一層，靠有沒有 <records> 區分。
明細不能塞進單頭的一格，故本模組把兩者拆開回傳，由匯出層寫進不同的 tab。

值的取法有一個例外：DIALOGINPUTLABEL 這類欄位的內文是 OID 或工號，
畫面上顯示的姓名放在 label 屬性（見 AGENTS.md 8.1）。只取內文的話，
稽核文件上會是一串工號沒有人看得懂，故兩者都有時輸出「姓名 (工號)」。
"""

import xml.etree.ElementTree as ET

# 被誤存成 pFormValue 的包裝層（5_ws_explorer 實測踩過）。第一層是這些就代表
# 這張單曾被整包回寫過，真正的表單在更裡面一層。
WRAPPER_TAGS = ('com.dsc.nana.services.webservice.FormCollection',
                'com.dsc.nana.services.webservice.FormInfo',
                'SimpleProcesses')

# 內文是代碼、顯示值放屬性的欄位，label 為畫面上看到的字
DISPLAY_ATTR = 'label'


class FormParseError(Exception):
    """表單 XML 無法解析；由呼叫端決定要標記還是略過，不靜默吞掉。"""


def _text(element):
    return element.text if element.text is not None else ''


def _value(element):
    """欄位的可讀值。內文與顯示值都有且不同時，合併呈現。"""
    text = _text(element).strip()
    label = (element.get(DISPLAY_ATTR) or '').strip()
    if label and label != text:
        return '%s (%s)' % (label, text) if text else label
    return text


def unwrap(raw_field_values):
    """剝掉可能存在的 FormCollection 包裝，回傳 (表單XML, 包裝層數)。"""
    text = (raw_field_values or '').strip()
    if not text:
        raise FormParseError('fieldValues 是空的')
    depth = 0
    while True:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            raise FormParseError('XML 解析失敗：%s' % err)
        if root.tag not in WRAPPER_TAGS:
            return text, depth
        inner = root.findtext('.//fieldValues')
        if not inner or not inner.strip():
            raise FormParseError('表單值被包在 %s 內且挖不出內層' % root.tag)
        text = inner.strip()
        depth += 1


def parse(raw_field_values):
    """把一張單的 fieldValues 拆成單頭欄位與表格明細。

    回傳 dict：
        formId    表單 id（XML 第一層標籤）
        fields    {欄位id: 值}，保留原始順序
        order     [欄位id]，供匯出時決定欄序
        grids     {表格id: [ {明細欄位id: 值}, ... ]}
        wrapped   被包壞的層數，0 代表正常
    """
    xml_text, depth = unwrap(raw_field_values)
    root = ET.fromstring(xml_text)

    fields = {}
    order = []
    grids = {}

    for element in root:
        records = element.find('records')
        if records is not None:
            rows = []
            for record in records.findall('record'):
                row = {}
                for item in record.findall('item'):
                    item_id = item.get('id') or item.tag
                    row[item_id] = _value(item)
                rows.append(row)
            grids[element.get('id') or element.tag] = rows
            continue

        field_id = element.get('id') or element.tag
        if field_id in fields:
            # 重複標籤在改單工具是致命的（會改錯欄位），但唯讀匯出只要不覆蓋掉
            # 先出現的值即可；保留第一筆並照樣往下走。
            continue
        fields[field_id] = _value(element)
        order.append(field_id)

    return {
        'formId': root.tag,
        'fields': fields,
        'order': order,
        'grids': grids,
        'wrapped': depth,
    }


def safe_parse(raw_field_values):
    """解析失敗不丟例外，改成回傳帶 error 的結果 —— 匯出時逐張標記，不整批中止。"""
    try:
        result = parse(raw_field_values)
        result['error'] = ''
        return result
    except FormParseError as err:
        return {'formId': '', 'fields': {}, 'order': [], 'grids': {},
                'wrapped': 0, 'error': str(err)}
    except ET.ParseError as err:
        return {'formId': '', 'fields': {}, 'order': [], 'grids': {},
                'wrapped': 0, 'error': 'XML 解析失敗：%s' % err}
