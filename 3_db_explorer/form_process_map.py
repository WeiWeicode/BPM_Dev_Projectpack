# -*- coding: utf-8 -*-
"""盤點「流程 → 表單」關聯：每支流程（最新 RELEASED 版）用到哪些表單。

關聯不存在任何外鍵欄位上，而且有兩個來源，涵蓋範圍不同：

  主來源  ActivityDefinition.formFieldAccessDefinitionOID
          → FormFieldAccessDefinition.formFieldAccessControl
          該段 XML 內第一層子標籤即 formId。只有「關卡設過欄位權限」才有值，
          因此有 87 支流程在這裡完全查不到。

  次來源  ProcessPackage.subjectTemplet
          主旨範本以 <#表單ID~~欄位ID> 引用表單欄位，可補回 49 支。
          但它會被複製流程時一起帶走而未更新，實測 47 支與主來源不一致，
          因此僅在主來源沒有結果時採用，且在輸出標記來源。

只取 formFieldAccessControl 前 1000 字元：formId 是開頭第一個標籤，
不需要整份權限清單，避免把 131728 筆大欄位全搬回來。

產出 out/form_process_map.csv 與 out/form_process_map.json，唯讀操作。
"""

import codecs
import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bpm_kb import config, db, extract  # noqa: E402

# <FormFieldAccessControl> 後的第一個標籤即表單 ID
FORM_ID_RE = re.compile(r'<FormFieldAccessControl>\s*<([A-Za-z_][\w.\-]*)>')

# 主旨範本的欄位引用語法：<#表單ID~~欄位ID>
SUBJECT_RE = re.compile(r'<#([A-Za-z_][\w.\-]*)~~')

# containerOID 一次帶太多會撐爆 SQL 參數上限，分批查
BATCH = 200

ACTIVITY_SQL = """
SELECT a.containerOID, a.id, a.activityDefinitionName, a.performType,
       LEFT(CAST(fa.formFieldAccessControl AS nvarchar(max)), 1000) AS control_head
FROM ActivityDefinition a
LEFT JOIN FormFieldAccessDefinition fa ON fa.OID = a.formFieldAccessDefinitionOID
WHERE a.containerOID IN (%s)
"""

SUBJECT_SQL = """
SELECT OID, subjectTemplet
FROM ProcessPackage
WHERE OID IN (%s)
"""

FORM_SQL = """
SELECT id, formDefinitionName, MAX(version) AS latest_version
FROM FormDefinition
WHERE publicationStatus = 'RELEASED'
GROUP BY id, formDefinitionName
"""


def _form_catalog(database):
    """表單 ID → 名稱與最新已發佈版本。"""
    catalog = {}
    for row in database.query(FORM_SQL):
        catalog[(row['id'] or '').strip()] = {
            'name': (row['formDefinitionName'] or '').strip(),
            'latestVersion': row['latest_version'],
        }
    return catalog


def _subject_form_ids(database, package_oids):
    """從主旨範本取出被引用的表單 ID，回傳 {ProcessPackage.OID: [formId, ...]}。"""
    result = {}
    for start in range(0, len(package_oids), BATCH):
        chunk = package_oids[start:start + BATCH]
        sql = SUBJECT_SQL % ','.join('?' for _ in chunk)
        for row in database.query(sql, tuple(chunk)):
            ids = []
            for fid in SUBJECT_RE.findall(row.get('subjectTemplet') or ''):
                if fid not in ids:
                    ids.append(fid)
            result[row['OID']] = ids
    return result


def _activities_by_container(database, container_oids):
    """一次撈多支流程的關卡，回傳 {containerOID: [關卡, ...]}。"""
    result = {}
    for start in range(0, len(container_oids), BATCH):
        chunk = container_oids[start:start + BATCH]
        sql = ACTIVITY_SQL % ','.join('?' for _ in chunk)
        for row in database.query(sql, tuple(chunk)):
            match = FORM_ID_RE.search(row.get('control_head') or '')
            result.setdefault(row['containerOID'], []).append({
                'id': (row['id'] or '').strip(),
                'name': (row['activityDefinitionName'] or '').strip(),
                'performType': (row['performType'] or '').strip(),
                'formId': match.group(1) if match else '',
            })
    return result


def build(database):
    """回傳每支流程一筆的關聯清單，依流程 ID 排序。"""
    packages = extract.list_processes(database, latest_only=True, released_only=True)
    catalog = _form_catalog(database)
    container_oids = [p['processDefinitionOID'] for p in packages
                      if p.get('processDefinitionOID')]
    activities = _activities_by_container(database, container_oids)
    subjects = _subject_form_ids(database, [p['OID'] for p in packages])

    records = []
    for package in packages:
        acts = activities.get(package.get('processDefinitionOID'), [])
        form_ids = []
        for act in acts:
            if act['formId'] and act['formId'] not in form_ids:
                form_ids.append(act['formId'])
        # 關卡沒設過欄位權限時主來源查不到，退回主旨範本
        subject_ids = subjects.get(package['OID'], [])
        source = 'formFieldAccessControl' if form_ids else (
            'subjectTemplet' if subject_ids else '')
        if not form_ids:
            form_ids = list(subject_ids)
        forms = [{
            'formId': fid,
            'formName': catalog.get(fid, {}).get('name', ''),
            'formLatestVersion': catalog.get(fid, {}).get('latestVersion'),
            # 流程引用得到、但表單主檔查不到已發佈版本 —— 版本脫節的徵兆
            'missingInFormDefinition': fid not in catalog,
        } for fid in sorted(form_ids)]
        records.append({
            'processId': (package.get('id') or '').strip(),
            'processName': (package.get('processPackageName') or '').strip(),
            'version': package.get('version'),
            'flowType': (package.get('flowType') or '').strip(),
            'createdTime': package.get('createdTime').isoformat()
                           if package.get('createdTime') else '',
            'authorName': (package.get('authorName') or '').strip(),
            'activityCount': len(acts),
            # 有些關卡（StartEvent / 通知節點）本來就不綁表單
            'activityWithFormCount': sum(1 for a in acts if a['formId']),
            'source': source,
            # 主旨範本另外提到、但與主來源不同的表單 —— 多半是複製流程沒改主旨
            'subjectOnlyFormIds': [f for f in subject_ids if f not in form_ids],
            'forms': forms,
        })
    return sorted(records, key=lambda r: r['processId'].lower())


def write_csv(records, path):
    """一支流程一列，表單清單以分號串接，方便直接匯入 Notion 資料庫。"""
    with io.open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['流程ID', '流程名稱', '版本', '流程類型', '關卡數',
                         '綁表單關卡數', '表單數', '表單ID清單', '表單名稱清單',
                         '關聯來源', '主旨範本另提到的表單', '缺表單主檔',
                         '建立時間', '建立者'])
        for r in records:
            writer.writerow([
                r['processId'], r['processName'], r['version'], r['flowType'],
                r['activityCount'], r['activityWithFormCount'], len(r['forms']),
                '; '.join(f['formId'] for f in r['forms']),
                '; '.join(f['formName'] or f['formId'] for f in r['forms']),
                r['source'], '; '.join(r['subjectOnlyFormIds']),
                '; '.join(f['formId'] for f in r['forms']
                          if f['missingInFormDefinition']),
                r['createdTime'], r['authorName'],
            ])


def main():
    if not os.path.isdir(config.OUT_DIR):
        os.makedirs(config.OUT_DIR)
    with db.Database() as database:
        records = build(database)
    csv_path = os.path.join(config.OUT_DIR, 'form_process_map.csv')
    json_path = os.path.join(config.OUT_DIR, 'form_process_map.json')
    write_csv(records, csv_path)
    with io.open(json_path, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(records, ensure_ascii=False, indent=2))
    by_fac = sum(1 for r in records if r['source'] == 'formFieldAccessControl')
    by_subject = sum(1 for r in records if r['source'] == 'subjectTemplet')
    unknown = sum(1 for r in records if not r['source'])
    mismatch = sum(1 for r in records
                   if r['source'] == 'formFieldAccessControl' and r['subjectOnlyFormIds'])
    orphan = sum(1 for r in records
                 for f in r['forms'] if f['missingInFormDefinition'])
    print('流程 %d 支：主來源 %d、主旨範本補回 %d、查不到 %d'
          % (len(records), by_fac, by_subject, unknown))
    print('主旨範本與主來源不一致 %d 支（多半是複製流程沒改主旨）' % mismatch)
    print('引用到但查無已發佈表單主檔的配對 %d 組' % orphan)
    print('已寫出 %s' % csv_path)
    print('已寫出 %s' % json_path)


if __name__ == '__main__':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    main()
