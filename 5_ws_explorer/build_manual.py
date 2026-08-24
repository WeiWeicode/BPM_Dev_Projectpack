# -*- coding: utf-8 -*-
"""把 WSDL 清單、實測結果、語意註記合成一份 API 手冊。

三份輸入各有各的權責，不要混在一起維護：
    out/WorkflowServiceService.json  介面契約，機器抓的，不手改
    out/probe_result.json            實測結果，機器跑的，不手改
    notes.json                       語意註記，人寫的

沒有註記的方法一律標「尚未分析」，不用名稱去編用途 ——
命名看起來很直白，但 fetchCanTraceProcSN 回逗號字串、
findManagerByAppLvl 把例外包在回傳值裡，都不是從名字看得出來的。

產出 docs/WorkflowService_API手冊.md。
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOCS_DIR = os.path.join(BASE_DIR, 'docs')

API_PATH = os.path.join(BASE_DIR, 'out', 'WorkflowServiceService.json')

PROBE_PATH = os.path.join(BASE_DIR, 'out', 'probe_result.json')

NOTES_PATH = os.path.join(BASE_DIR, 'notes.json')

MANUAL_PATH = os.path.join(DOCS_DIR, 'WorkflowService_API手冊.md')

CONFIDENCE = {
    'verified': '✅ 已實測',
    'external': '☑️ 已在既有服務驗證',
    'guess': '⚠️ 未實測，僅推測',
}

STATUS = {
    'ok': '實測成功',
    'fault': '實測失敗（SOAP Fault）',
    'error': '實測失敗（連線層）',
    'soft_error': '假成功（回傳值是例外）',
    'skipped': '未實測',
}

PREFACE = """
## 呼叫前必讀

### 這是 rpc/encoded，不是 document/literal

Apache Axis 1.3 產生的舊式 SOAP。實務上的三個後果：

1. **參數是位置對應**，順序錯了不會報錯，只會拿到錯的結果或空值。
   正確順序看每支方法的 `parameterOrder`（本手冊列出的順序已經是對的）。
2. **`SOAPAction` 是空字串**，分派靠 body 內的方法名。
3. **Python 的 zeep 接不上這個服務**（不支援 SOAP encoding）。
   本專案用 `ws_client.py` 手刻 envelope；Node 端的 `soap` 套件則可正常運作。

envelope 長這樣：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <ns1:findFormOIDsOfProcess xmlns:ns1="http://webservice.nana.dsc.com/">
      <pProcessPackageId xsi:type="xsd:string">SP_DetectionOPProcess</pProcessPackageId>
    </ns1:findFormOIDsOfProcess>
  </soapenv:Body>
</soapenv:Envelope>
```

### 回傳的 `string` 幾乎都不是純字串

41 支方法宣告回傳 `string`，實際內容有四種，**WSDL 完全看不出來**：

| 實際內容 | 例子 |
|:---|:---|
| XStream 序列化的 Java 物件 XML | `fetchProcInstances`、`fetchOrgUnitOfUserId` |
| 屬性式 XML（風格不同） | `getSubstituteState` |
| 逗號分隔字串 | `fetchCanTraceProcSN` |
| 純量文字 | `findFormOIDsOfProcess`、`fetchProcessContextVariable`（三參數版） |

`fetchFormInstance*` 更是「XML 字串包在 XML 裡」，`fieldValues` 要解兩層。

### 失敗有三種，其中一種不會丟例外

| 型態 | 表現 | 呼叫端要做什麼 |
|:---|:---|:---|
| SOAP Fault | HTTP 500，`faultstring` 帶 Java 例外 | 正常攔截 |
| 業務性拒絕 | 也是 Fault，但訊息講得很清楚（例如「單子還在跑，沒有作廢意見」） | 讀訊息，別一律當系統錯誤 |
| **假成功** | **HTTP 200，回傳字串本身是 `<NotFoundException>...</NotFoundException>`** | **必須額外檢查回傳內容** |

第三種目前已知發生在 `findManagerByAppLvl`。只判斷有無丟例外的呼叫端會把
例外訊息當成資料收下。

### 表單欄位值（`pFormFieldValue`）的格式

開單時 `pFormFieldValue` 是一段 XML 字串，以表單 ID 為根，每個欄位一個標籤：

```xml
<SP_DetectionOPForm>
  <EmailSubjectTextBox id="EmailSubjectTextBox" dataType="java.lang.String" perDataProId="">主旨</EmailSubjectTextBox>
  <ControlPlanApplyDate id="ControlPlanApplyDate" dataType="java.util.Date">2026/08/24</ControlPlanApplyDate>
</SP_DetectionOPForm>
```

存進去之後由 `fetchFormInstance*` 讀回來時是同樣的結構，已實測來回一致。

### 已知地雷：錯的欄位 id 不會被擋，會延後爆炸

`invokeProcess` **不驗證** `pFormFieldValue` 裡的欄位 id 是否存在於表單定義。
不存在的欄位照樣寫進單子，開單成功、回傳正常。等到有人呼叫
`fetchUniFormatFormInstanceWithProcSerlNo` 讀這張單時才會炸：

```
java.lang.IllegalArgumentException:
Argument 'pFieldId = EmailSubjectTextBox' cannot find ElementDefinition in FormDefinition.
```

而 `fetchFormInstanceWithProcSerlNo`（非 UniFormat 版）讀同一張單卻毫無問題 ——
所以這種壞單可能很久都不會被發現。

**開單前先用 `getFormFieldTemplate(pFormDefOID)` 對過欄位 id。**
""".strip()


def _load(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def _note_key(operation):
    """註記以方法名為 key。多載共用一則註記，差異寫在註記內文。"""
    return operation['name']


def _probe_index(probe):
    """實測結果以 inputMessage 為 key，多載才分得開。"""
    index = {}
    for item in probe['results']:
        index[item['inputMessage'] or item['name']] = item
    return index


def _signature(operation):
    args = ', '.join('%s %s' % (part['type'], part['name'])
                     for part in operation['parameters'])
    returns = operation['returns'][0]['type'] if operation['returns'] else 'void'
    return '%s(%s) : %s' % (operation['name'], args, returns)


def _render_operation(operation, note, probed):
    lines = []
    title = operation['name']
    if operation['inputMessage'] and operation['inputMessage'].endswith('Request1'):
        title = '%s（多載：%d 參數）' % (operation['name'], len(operation['parameters']))
    elif operation['inputMessage'] != '%sRequest' % operation['name']:
        title = '%s（%s）' % (operation['name'], operation['inputMessage'])

    lines.append('### %s' % title)
    lines.append('')
    lines.append('```')
    lines.append(_signature(operation))
    lines.append('```')
    lines.append('')

    confidence = CONFIDENCE.get((note or {}).get('信心'), '⚠️ 尚未分析')
    status = STATUS.get(probed['status'], probed['status']) if probed else '未實測'
    lines.append('| 信心 | 實測狀態 | 耗時 |')
    lines.append('|:---|:---|---:|')
    lines.append('| %s | %s | %s |' % (
        confidence, status,
        '%d ms' % probed['elapsedMs'] if probed and 'elapsedMs' in probed else '—'))
    lines.append('')

    if not note:
        lines.append('**尚未分析。** 實測狀態如上表；用途與參數語意未確認，不臆測。')
        if probed and probed['status'] == 'skipped':
            lines.append('')
            lines.append('未實測原因：%s' % probed.get('reason', ''))
        lines.append('')
        return lines

    lines.append('**用途**：%s' % note.get('用途', '未確認'))
    lines.append('')

    described = note.get('參數', {})
    if operation['parameters']:
        lines.append('| 參數 | 型別 | 說明 |')
        lines.append('|:---|:---|:---|')
        for part in operation['parameters']:
            lines.append('| `%s` | %s | %s |' % (
                part['name'], part['type'],
                described.get(part['name'], '未確認')))
        lines.append('')

    lines.append('**回傳**：%s' % note.get('回傳', '未確認'))
    lines.append('')
    if note.get('備註'):
        lines.append('> %s' % note['備註'])
        lines.append('')
    if probed and probed.get('payload'):
        lines.append('回傳樣本：`%s`' % probed['payload'])
        lines.append('')
    if probed and probed['status'] in ('fault', 'error'):
        message = probed.get('faultString') or probed.get('error') or ''
        lines.append('實測錯誤：`%s`' % message.replace('\n', ' ')[:300])
        lines.append('')
    return lines


def build():
    api = _load(API_PATH)
    probe = _load(PROBE_PATH)
    notes = dict((key, value) for key, value in _load(NOTES_PATH).items()
                 if not key.startswith('_'))
    probed = _probe_index(probe)

    documented = [item for item in api['operations'] if _note_key(item) in notes]
    undocumented = [item for item in api['operations'] if _note_key(item) not in notes]

    lines = []
    lines.append('# 鼎新 BPM WorkflowService API 手冊')
    lines.append('')
    lines.append('| 項目 | 值 |')
    lines.append('|:---|:---|')
    lines.append('| Endpoint | `%s` |' % probe['endpoint'])
    lines.append('| 方法總數 | %d |' % api['operationCount'])
    lines.append('| 已寫下語意 | %d |' % len(documented))
    lines.append('| 實測成功 | %d |' % probe['summary'].get('ok', 0))
    lines.append('| 實測時間 | %s |' % probe['probedAt'])
    lines.append('')
    lines.append('本手冊由 `build_manual.py` 合成，勿直接編輯 ——')
    lines.append('語意註記請改 `notes.json`，介面契約與實測結果由工具重跑產生。')
    lines.append('')
    lines.append('> **190 正式區未曾連線。** 以下全部來自 191 測試區。')
    lines.append('')
    lines.append(PREFACE)
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 方法索引')
    lines.append('')
    lines.append('| 方法 | 信心 | 實測 |')
    lines.append('|:---|:---|:---|')
    for operation in api['operations']:
        note = notes.get(_note_key(operation))
        item = probed.get(operation['inputMessage'])
        lines.append('| `%s` | %s | %s |' % (
            operation['name'],
            CONFIDENCE.get((note or {}).get('信心'), '⚠️ 尚未分析'),
            STATUS.get(item['status'], '—') if item else '—'))
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 已分析的方法')
    lines.append('')
    for operation in documented:
        lines.extend(_render_operation(operation,
                                       notes.get(_note_key(operation)),
                                       probed.get(operation['inputMessage'])))
    lines.append('---')
    lines.append('')
    lines.append('## 尚未分析的方法')
    lines.append('')
    lines.append('以下 %d 支只有介面契約，沒有經過驗證的用途說明。' % len(undocumented))
    lines.append('多數是有副作用的方法（開單、簽核、轉派、作廢），需要可拋棄的測試單才能驗。')
    lines.append('')
    lines.append('| 方法 | 參數 | 回傳 | 未實測原因 |')
    lines.append('|:---|:---|:---|:---|')
    for operation in undocumented:
        item = probed.get(operation['inputMessage']) or {}
        args = ', '.join('`%s`' % part['name'] for part in operation['parameters']) or '（無）'
        returns = operation['returns'][0]['type'] if operation['returns'] else 'void'
        lines.append('| `%s` | %s | `%s` | %s |' % (
            operation['name'], args, returns, item.get('reason', '—')))
    lines.append('')

    if not os.path.isdir(DOCS_DIR):
        os.makedirs(DOCS_DIR)
    with open(MANUAL_PATH, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
    print('寫出 %s（%d 支已分析 / %d 支未分析）'
          % (MANUAL_PATH, len(documented), len(undocumented)))


if __name__ == '__main__':
    build()
