# -*- coding: utf-8 -*-
"""對 191 測試區實測 WorkflowService，記錄每支方法真正的行為。

**只跑唯讀（read）方法。** 有副作用的方法（開單、簽核、作廢、改代理人…）
預設不呼叫，必須用 --method 指名，並加上 --allow-write 才會送出 ——
這類呼叫會在測試區產生真實的簽核單與待辦，不是可以整批掃過去的東西。

分級依方法名稱的動詞，但**動詞不夠用的一律歸到 write**（寧可少跑不要誤觸）：
`management*` 這種名字看不出在管什麼的，就不自動跑。

參數值取自 seeds.json。缺種子的方法標 skipped 並列出缺哪個參數，
不會亂餵值去試 —— 餵錯值拿到空回應，會被誤讀成「這方法沒用」。

產出：
    out/probe_result.json          每支方法的實測結果（含錯誤原文）
    out/probe_result.md            人看的結果摘要
    out/payloads/<方法>.xml        回傳字串的完整樣本，供推導結構
"""

import argparse
import datetime
import json
import os
import re
import time

import ws_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUT_DIR = os.path.join(BASE_DIR, 'out')

PAYLOAD_DIR = os.path.join(OUT_DIR, 'payloads')

SEEDS_PATH = os.path.join(BASE_DIR, 'seeds.json')

# 明確列舉唯讀動詞。沒列到的一律當成有副作用。
READ_VERBS = ('fetch', 'get', 'find', 'count', 'is', 'check')

# 就算動詞是唯讀，這些仍要人工確認（名稱語意不明或可能改狀態）
SUSPECT = ('management',)


def classify(name):
    """回傳 read / write。判斷依據只有名稱，因此保守 —— 不確定就算 write。"""
    verb = re.match(r'[a-z]+', name)
    if verb is None:
        return 'write'
    verb = verb.group()
    if verb in SUSPECT:
        return 'write'
    return 'read' if verb in READ_VERBS else 'write'


def _load_seeds():
    """回傳 (共用種子, 依方法覆寫)。底線開頭的 key 是說明欄位，不是種子。"""
    with open(SEEDS_PATH, 'r', encoding='utf-8') as handle:
        seeds = json.load(handle)
    overrides = seeds.get('_overrides', {})
    shared = dict((key, value) for key, value in seeds.items() if not key.startswith('_'))
    return shared, overrides


def _bind(operation, seeds, overrides):
    """回傳 (參數 dict, 缺少的參數名, 有無套用覆寫)。"""
    applied = overrides.get(operation['name'], {})
    params = {}
    missing = []
    for part in operation['parameters']:
        if part['name'] in applied:
            params[part['name']] = applied[part['name']]
        elif part['name'] in seeds:
            params[part['name']] = seeds[part['name']]
        else:
            missing.append(part['name'])
    return params, missing, bool(applied)


def _payload_name(operation):
    """多載要能分辨，用 inputMessage 當檔名（invokeProcessRequest1）。"""
    return operation['inputMessage'] or operation['name']


def _shape(text):
    """把回傳的 XStream XML 壓成標籤輪廓，方便一眼看出資料結構。"""
    if not text:
        return None
    stripped = text.strip()
    if not stripped.startswith('<'):
        return '（非 XML 純值）'
    tags = []
    for tag in re.findall(r'<([A-Za-z][\w.$]*)[\s>/]', stripped):
        if tag not in tags:
            tags.append(tag)
    return ' > '.join(tags[:12])


def probe(service, operation, seeds, overrides, allow_write):
    """實測單一方法。錯誤原樣記錄，不轉成空結果。"""
    level = classify(operation['name'])
    record = {
        'name': operation['name'],
        'inputMessage': operation['inputMessage'],
        'level': level,
        'parameters': [part['name'] for part in operation['parameters']],
        'returnType': operation['returns'][0]['type'] if operation['returns'] else None,
    }

    if level == 'write' and not allow_write:
        record['status'] = 'skipped'
        record['reason'] = '有副作用，未經指名不自動呼叫'
        return record

    params, missing, overridden = _bind(operation, seeds, overrides)
    record['seedOverridden'] = overridden
    if missing:
        record['status'] = 'skipped'
        record['reason'] = '缺種子值：%s' % ', '.join(missing)
        return record

    record['sentParameters'] = params
    started = time.time()
    try:
        value, raw = service.call_operation(operation, params)
    except ws_client.SoapFault as fault:
        record['status'] = 'fault'
        record['faultCode'] = fault.code
        record['faultString'] = fault.message
        record['elapsedMs'] = int((time.time() - started) * 1000)
        return record
    except Exception as error:  # 連線層問題也要留痕，不能靜默跳過
        record['status'] = 'error'
        record['error'] = '%s: %s' % (type(error).__name__, error)
        record['elapsedMs'] = int((time.time() - started) * 1000)
        return record

    record['elapsedMs'] = int((time.time() - started) * 1000)
    record['status'] = 'ok'
    record['returnLength'] = len(value) if value else 0
    record['returnShape'] = _shape(value)
    record['returnPreview'] = (value or '')[:200]
    record['rawLength'] = len(raw)

    # 有些方法把例外包成回傳字串而非 SOAP Fault，照收會被當成資料
    if value and value.lstrip().startswith('<') and 'Exception>' in value[:300]:
        record['status'] = 'soft_error'
        record['softError'] = value.strip()[:300]

    if value:
        path = os.path.join(PAYLOAD_DIR, '%s.xml' % _payload_name(operation))
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(value)
        record['payload'] = os.path.relpath(path, BASE_DIR).replace('\\', '/')
    return record


def to_markdown(result):
    lines = []
    lines.append('# WorkflowService 實測結果')
    lines.append('')
    lines.append('> 由 `probe_api.py` 對 %s 實測產生。' % result['endpoint'])
    lines.append('> 只自動呼叫唯讀方法；有副作用者需 `--method` 指名並加 `--allow-write`。')
    lines.append('')
    counts = result['summary']
    lines.append('| 狀態 | 數量 | 意義 |')
    lines.append('|:---|---:|:---|')
    lines.append('| ok | %d | 呼叫成功，回傳樣本已存於 `out/payloads/` |' % counts.get('ok', 0))
    lines.append('| fault | %d | 服務回 SOAP Fault，多半是參數值不對而非方法不能用 |' % counts.get('fault', 0))
    lines.append('| error | %d | 連線或解析層失敗 |' % counts.get('error', 0))
    lines.append('| soft_error | %d | HTTP 200 但回傳字串本身是例外，**不是資料** |' % counts.get('soft_error', 0))
    lines.append('| skipped | %d | 有副作用或缺種子值，未呼叫 |' % counts.get('skipped', 0))
    lines.append('')
    lines.append('實測時間：%s' % result['probedAt'])
    lines.append('')

    lines.append('## 呼叫成功')
    lines.append('')
    lines.append('| 方法 | 耗時 | 回傳長度 | 回傳結構輪廓 |')
    lines.append('|:---|---:|---:|:---|')
    for item in result['results']:
        if item['status'] == 'ok':
            lines.append('| `%s` | %d ms | %s | %s |' % (
                item['name'], item['elapsedMs'],
                item['returnLength'] or '—',
                item['returnShape'] or '（空回傳）'))
    lines.append('')

    soft = [item for item in result['results'] if item['status'] == 'soft_error']
    if soft:
        lines.append('## 假成功（回傳字串裡包著例外）')
        lines.append('')
        lines.append('呼叫端若只判斷有沒有丟例外，會把下列訊息當成正常資料收下。')
        lines.append('')
        lines.append('| 方法 | 回傳內容 |')
        lines.append('|:---|:---|')
        for item in soft:
            lines.append('| `%s` | %s |' % (item['name'],
                                            item['softError'].replace('\n', ' ')[:160]))
        lines.append('')

    faults = [item for item in result['results'] if item['status'] in ('fault', 'error')]
    if faults:
        lines.append('## 呼叫失敗')
        lines.append('')
        lines.append('| 方法 | 錯誤 |')
        lines.append('|:---|:---|')
        for item in faults:
            message = item.get('faultString') or item.get('error') or ''
            lines.append('| `%s` | %s |' % (item['name'], message.replace('\n', ' ')[:160]))
        lines.append('')

    skipped = [item for item in result['results'] if item['status'] == 'skipped']
    if skipped:
        lines.append('## 未呼叫')
        lines.append('')
        lines.append('| 方法 | 分級 | 原因 |')
        lines.append('|:---|:---|:---|')
        for item in skipped:
            lines.append('| `%s` | %s | %s |' % (item['name'], item['level'], item['reason']))
        lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='對 191 測試區實測 WorkflowService')
    parser.add_argument('--endpoint', default=ws_client.DEFAULT_ENDPOINT)
    parser.add_argument('--method', action='append',
                        help='只跑指定方法，可重複；不給則跑全部唯讀方法')
    parser.add_argument('--allow-write', action='store_true',
                        help='允許呼叫有副作用的方法。只在 --method 指名時生效')
    args = parser.parse_args()

    if args.allow_write and not args.method:
        parser.error('--allow-write 必須搭配 --method 指名方法，不接受整批寫入')

    if '10.10.130.190' in args.endpoint:
        parser.error('190 正式區不在本工具的作用範圍')

    service = ws_client.WorkflowService(endpoint=args.endpoint)
    seeds, overrides = _load_seeds()

    for directory in (OUT_DIR, PAYLOAD_DIR):
        if not os.path.isdir(directory):
            os.makedirs(directory)

    targets = service.operations
    if args.method:
        wanted = set(args.method)
        targets = [item for item in targets
                   if item['name'] in wanted or item['inputMessage'] in wanted]
        if not targets:
            parser.error('找不到方法：%s' % ', '.join(sorted(wanted)))

    results = []
    for operation in targets:
        record = probe(service, operation, seeds, overrides, args.allow_write)
        results.append(record)
        print('%-8s %-48s %s' % (
            record['status'], record['name'],
            record.get('reason') or record.get('faultString')
            or record.get('error') or record.get('softError')
            or ('%s 字元' % record.get('returnLength', 0))))

    summary = {}
    for record in results:
        summary[record['status']] = summary.get(record['status'], 0) + 1

    result = {
        'endpoint': args.endpoint,
        'probedAt': datetime.datetime.now().isoformat(timespec='seconds'),
        'seedSource': 'seeds.json',
        'summary': summary,
        'results': results,
    }

    with open(os.path.join(OUT_DIR, 'probe_result.json'), 'w', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, 'probe_result.md'), 'w', encoding='utf-8') as handle:
        handle.write(to_markdown(result))

    print('')
    print('統計：%s' % summary)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
