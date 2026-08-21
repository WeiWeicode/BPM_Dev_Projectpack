# -*- coding: utf-8 -*-
"""資料庫探索：不靠猜測，直接問資料庫「表單與流程的 XML 到底存在哪」。

策略：
  1. 掃出所有資料表與筆數。
  2. 找出所有大文字欄位（ntext / text / nvarchar(max)）。
  3. 每個欄位只抽前幾筆讀開頭字元，在 Python 端判斷是否為 <com.dsc.*> 序列化 XML。
     刻意不用 WHERE ... LIKE 過濾，否則每個欄位都會觸發一次全表掃描。
  4. 順帶取外鍵關聯，作為理解資料模型的骨架。
結果寫成 docs/schema/*.json，供後續萃取與文件產生使用。
"""

import io
import json
import os
import sys

from . import config, db

XML_HEAD_LEN = 200
DSC_PREFIX = '<com.dsc.'
SAMPLE_ROWS = 20

# 大文字欄位的型別
BIG_TEXT_TYPES = ('ntext', 'text', 'nvarchar', 'varchar', 'xml')
BIG_TEXT_MIN_LEN = 4000  # nvarchar(max) 的 max_length 為 -1，另行判斷


def list_tables(database):
    """所有使用者資料表與概略筆數（取自 sys.partitions，免全表掃描）。"""
    sql = """
    SELECT t.name AS table_name,
           SUM(CASE WHEN p.index_id IN (0, 1) THEN p.rows ELSE 0 END) AS row_count
    FROM sys.tables t
    JOIN sys.partitions p ON p.object_id = t.object_id
    GROUP BY t.name
    ORDER BY t.name
    """
    return database.query(sql)


def list_columns(database, table_name=None):
    """欄位清單；不指定 table 時回傳全庫欄位。"""
    sql = """
    SELECT t.name AS table_name, c.name AS column_name, ty.name AS data_type,
           c.max_length, c.is_nullable, c.column_id
    FROM sys.tables t
    JOIN sys.columns c ON c.object_id = t.object_id
    JOIN sys.types ty ON ty.user_type_id = c.user_type_id
    """
    params = ()
    if table_name:
        sql += ' WHERE t.name = ?'
        params = (table_name,)
    sql += ' ORDER BY t.name, c.column_id'
    return database.query(sql, params)


def list_foreign_keys(database):
    """外鍵關聯（鼎新多以 OID 字串關聯，可能很少，仍先取回作參考）。"""
    sql = """
    SELECT fk.name AS fk_name,
           tp.name AS parent_table, cp.name AS parent_column,
           tr.name AS ref_table,    cr.name AS ref_column
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    JOIN sys.tables tp ON tp.object_id = fkc.parent_object_id
    JOIN sys.columns cp ON cp.object_id = fkc.parent_object_id AND cp.column_id = fkc.parent_column_id
    JOIN sys.tables tr ON tr.object_id = fkc.referenced_object_id
    JOIN sys.columns cr ON cr.object_id = fkc.referenced_object_id AND cr.column_id = fkc.referenced_column_id
    ORDER BY tp.name, fk.name
    """
    return database.query(sql)


def _is_big_text(column):
    if column['data_type'] not in BIG_TEXT_TYPES:
        return False
    if column['data_type'] in ('ntext', 'text', 'xml'):
        return True
    return column['max_length'] == -1 or column['max_length'] >= BIG_TEXT_MIN_LEN


def find_definition_columns(database, tables=None, progress=False):
    """抽樣每個大文字欄位，找出存放 com.dsc.* 序列化 XML 的欄位。

    回傳 list[dict]：table_name / column_name / java_class / row_count / sample_head。
    """
    columns = list_columns(database)
    counts = {row['table_name']: row['row_count'] for row in list_tables(database)}
    candidates = [c for c in columns
                  if counts.get(c['table_name'])
                  and _is_big_text(c)
                  and (not tables or c['table_name'] in tables)]

    hits = []
    for index, column in enumerate(candidates, 1):
        table_name = column['table_name']
        expr = db.big_text('[%s]' % column['column_name'])
        sql = ('SELECT TOP %d LEFT(%s, %d) AS head FROM [%s] WHERE [%s] IS NOT NULL'
               % (SAMPLE_ROWS, expr, XML_HEAD_LEN, table_name, column['column_name']))
        if progress:
            sys.stderr.write('\r  掃描 %d/%d %s.%s%s'
                             % (index, len(candidates), table_name,
                                column['column_name'], ' ' * 20))
            sys.stderr.flush()
        try:
            rows = database.query(sql)
        except Exception:
            continue  # 型別無法轉換的欄位直接略過
        for row in rows:
            head = (row['head'] or '').strip()
            if not head.startswith(DSC_PREFIX):
                continue
            hits.append({
                'table_name': table_name,
                'column_name': column['column_name'],
                'java_class': _java_class(head),
                'row_count': counts.get(table_name, 0),
                'sample_head': head[:120],
            })
            break
    if progress:
        sys.stderr.write('\r' + ' ' * 78 + '\r')
        sys.stderr.flush()
    return hits


def _java_class(head):
    """從 <com.dsc.nana.domain.form.FormDefinition id="1"> 取出類別全名。"""
    if not head.startswith(DSC_PREFIX):
        return ''
    tag = head[1:]
    for stop in (' ', '>', '\n', '\r', '\t'):
        index = tag.find(stop)
        if index != -1:
            tag = tag[:index]
    return tag


def snapshot(database, path=None, progress=True):
    """把探索結果存成 JSON 快照。"""
    config.ensure_dirs()
    data = {
        'connection': config.describe(database.settings),
        'tables': list_tables(database),
        'columns': list_columns(database),
        'foreign_keys': list_foreign_keys(database),
        'definition_columns': find_definition_columns(database, progress=progress),
    }
    path = path or os.path.join(config.SCHEMA_DIR, 'schema_snapshot.json')
    with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return path, data


def load_snapshot(path=None):
    path = path or os.path.join(config.SCHEMA_DIR, 'schema_snapshot.json')
    if not os.path.isfile(path):
        return None
    with io.open(path, encoding='utf-8') as fh:
        return json.load(fh)
