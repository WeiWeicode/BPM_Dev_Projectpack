# -*- coding: utf-8 -*-
"""權限寫入引擎。

**這是本工具集唯一會寫資料庫的地方。** `bpm_kb.db.Database` 維持 readonly=True，
本模組自行開一條可寫連線，讓「唯讀」在型別層面就看得出來。

只改 formFieldAccessControl 內既有元件的權限值，不碰任何結構。
編輯採最小字串替換，未觸及的部分位元組不變 —— 與 1_xml_tool 的無損原則一致。

權限模型（實測 20000 筆 + 設計師 UI 對照）：
    ENABLED / INVISIBLE / FULL_CONTROL  存在字串中
    DISABLE                             **不是值，是把該元件從字串中移除**
    INVALIDITY                          資料庫中從未出現，格式未知，不支援
"""

import hashlib
import io
import json
import os
import re
import time

from . import cache, service, settings

settings.ensure_bpm_kb()

from bpm_kb import config, extract  # noqa: E402
from bpm_kb.db import big_text  # noqa: E402

# DISABLE 代表移除該元件的權限設定，BPM 設計師會顯示成「唯讀(Disable)」
REMOVE = 'DISABLE'
STORED_VALUES = ('ENABLED', 'INVISIBLE', 'FULL_CONTROL')
ALLOWED_VALUES = STORED_VALUES + (REMOVE,)

ACTIVITY_SQL = """
SELECT a.OID AS activity_oid, a.id AS activity_id,
       a.activityDefinitionName AS activity_name,
       a.formFieldAccessDefinitionOID AS perm_oid
FROM ActivityDefinition a
WHERE a.containerOID = ? AND a.id = ?
"""

SHARE_SQL = ('SELECT COUNT(*) FROM ActivityDefinition '
             'WHERE formFieldAccessDefinitionOID = ?')

READ_SQL = ('SELECT %s AS ctl, objectVersion FROM FormFieldAccessDefinition '
            'WHERE OID = ?' % big_text('formFieldAccessControl'))


class WriteError(Exception):
    """寫入被拒或失敗。message 會原樣回給使用者，要寫得能看懂。"""


# ---------------------------------------------------------------- 定位

def _process_row(process_id, host=None):
    row = service._find(service._process_rows(host), 'id', process_id)
    if row is None:
        raise WriteError('找不到已發佈的流程：%s' % process_id)
    return row


def _locate(process_id, activity_id, host=None):
    """找出關卡與它的權限定義列，並跑完所有前置檢查。"""
    if not settings.ENABLE_WRITE:
        raise WriteError('寫入功能未啟用（需設定 BPM_VIEWER_ENABLE_WRITE=1）')

    entry = settings.host_entry(host or settings.DEFAULT_HOST)
    if not settings.host_writable(entry[0]):
        # 正式區預設不在 WRITABLE_HOSTS 中，切過去就寫不下去
        raise WriteError('主機 %s（%s）不允許寫入' % (entry[1], entry[2]))

    if process_id not in settings.WRITABLE_PROCESSES:
        raise WriteError('流程 %s 不在寫入白名單中（BPM_VIEWER_WRITABLE_PROCESSES）'
                         % process_id)

    row = _process_row(process_id, host)
    container_oid = (row.get('processDefinitionOID') or '').strip()
    with service.connect(host) as database:
        found = database.query(ACTIVITY_SQL, (container_oid, activity_id))
    if not found:
        raise WriteError('流程 %s 中找不到關卡 %s' % (process_id, activity_id))

    activity = found[0]
    perm_oid = (activity.get('perm_oid') or '').strip()
    if not perm_oid:
        raise WriteError('關卡 %s 沒有權限定義列，代表它未掛表單' % activity_id)

    with service.connect(host) as database:
        shared = database.scalar(SHARE_SQL, (perm_oid,))
    if shared != 1:
        # 線上最多有一列被 24765 個關卡共用，改下去就是災難
        raise WriteError('這筆權限定義被 %d 個關卡共用，拒絕修改（只允許 1:1）' % shared)

    with service.connect(host) as database:
        rows = database.query(READ_SQL, (perm_oid,))
    if not rows:
        raise WriteError('讀不到權限定義列 %s' % perm_oid)

    return {
        'host': entry[0],
        'process_id': process_id,
        'activity_id': (activity['activity_id'] or '').strip(),
        'activity_name': (activity['activity_name'] or '').strip(),
        'perm_oid': perm_oid,
        'ctl': rows[0]['ctl'],
        'object_version': rows[0]['objectVersion'],
    }


# ---------------------------------------------------------------- 字串編輯

def _form_id(ctl):
    match = service.FORM_ID_RE.search(ctl or '')
    return match.group(1) if match else ''


def _current(ctl, field_id):
    """目前的權限值；不在字串中回 DISABLE（設計師顯示為唯讀）。"""
    match = re.search(r'<%s>([^<]*)</%s>' % (re.escape(field_id), re.escape(field_id)), ctl)
    return match.group(1) if match else REMOVE


def _edit(ctl, field_id, value):
    """最小字串編輯：替換值、移除標籤，或在結尾前插入新標籤。"""
    tag_re = re.compile(r'<%s>[^<]*</%s>' % (re.escape(field_id), re.escape(field_id)))
    present = tag_re.search(ctl) is not None

    if value == REMOVE:
        return tag_re.sub('', ctl) if present else ctl

    new_tag = '<%s>%s</%s>' % (field_id, value, field_id)
    if present:
        return tag_re.sub(new_tag, ctl)

    # 原本是唯讀（未列出），現在要給權限 -> 插在表單區塊結尾前
    form_id = _form_id(ctl)
    closing = '</%s>' % form_id
    index = ctl.rfind(closing)
    if index == -1:
        raise WriteError('權限字串格式異常，找不到 %s' % closing)
    return ctl[:index] + new_tag + ctl[index:]


def _token(ctl):
    """以目前內容的雜湊當令牌：套用時若內容已被別人改過就擋下來。"""
    return hashlib.sha256((ctl or '').encode('utf-8')).hexdigest()[:16]


# ---------------------------------------------------------------- 預覽

def preview(process_id, activity_id, items, host=None):
    """回傳每個元件的 舊值 → 新值，以及套用所需的 token。不寫入任何東西。"""
    located = _locate(process_id, activity_id, host)
    ctl = located['ctl']
    form_id = _form_id(ctl)

    known = {}
    if form_id:
        with service.connect(host) as database:
            known = extract.form_index(database, {form_id}).get(form_id, {})

    changes, new_ctl = [], ctl
    for item in items:
        field_id = (item.get('id') or '').strip()
        value = (item.get('permission') or '').strip().upper()
        if value not in ALLOWED_VALUES:
            raise WriteError('不支援的權限值：%s（可用：%s）'
                             % (value, '、'.join(ALLOWED_VALUES)))
        if not field_id:
            raise WriteError('元件 ID 不可為空')
        # 只能改表單裡真的存在的元件，否則會製造 orphaned 資料
        if known and field_id not in known:
            raise WriteError('元件 %s 不在表單 %s 的定義中，拒絕寫入' % (field_id, form_id))

        before = _current(new_ctl, field_id)
        new_ctl = _edit(new_ctl, field_id, value)
        meta = known.get(field_id) or {}
        changes.append({
            'id': field_id,
            'name': meta.get('name', ''),
            'type': meta.get('type', ''),
            'before': before,
            'after': value,
            'changed': before != value,
        })

    return {
        'host': located['host'],
        'process_id': process_id,
        'activity_id': located['activity_id'],
        'activity_name': located['activity_name'],
        'form_id': form_id,
        'perm_oid': located['perm_oid'],
        'object_version': located['object_version'],
        'changes': changes,
        'changed_count': sum(1 for c in changes if c['changed']),
        'token': _token(ctl),
        'preview_ctl_length': len(new_ctl),
    }


# ---------------------------------------------------------------- 備份與稽核

def _backup(perm_oid, ctl):
    if not os.path.isdir(settings.BACKUP_DIR):
        os.makedirs(settings.BACKUP_DIR)
    backup_id = '%s_%s' % (perm_oid, time.strftime('%Y%m%d-%H%M%S'))
    path = os.path.join(settings.BACKUP_DIR, backup_id + '.xml')
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(ctl)
    # 備份寫不出來就不准往下走
    if not os.path.isfile(path):
        raise WriteError('備份失敗，中止寫入')
    return backup_id, path


def _audit(entry):
    if not os.path.isdir(settings.BACKUP_DIR):
        os.makedirs(settings.BACKUP_DIR)
    with io.open(settings.AUDIT_LOG, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')


def _writable_connection(host=None):
    """唯一一條可寫連線。刻意不與 bpm_kb.Database 共用。"""
    import pyodbc
    return pyodbc.connect(config.connection_string(service.db_settings(host)),
                          timeout=15)


def _update(perm_oid, new_ctl, bump_from=None, host=None):
    """單筆 UPDATE；rowcount 不是 1 一律 rollback。"""
    sql = 'UPDATE FormFieldAccessDefinition SET formFieldAccessControl = ?'
    params = [new_ctl]
    if bump_from is not None:
        sql += ', objectVersion = ?'
        params.append(bump_from + 1)
    sql += ' WHERE OID = ?'
    params.append(perm_oid)

    connection = _writable_connection(host)
    try:
        cursor = connection.cursor()
        cursor.execute(sql, tuple(params))
        affected = cursor.rowcount
        if affected != 1:
            connection.rollback()
            raise WriteError('影響 %d 列（預期 1），已 rollback' % affected)
        connection.commit()
    finally:
        connection.close()


# ---------------------------------------------------------------- 套用

def apply(process_id, activity_id, items, token, actor='', host=None):
    """實際寫入。token 必須來自 preview，且期間內容未被他人改動。"""
    located = _locate(process_id, activity_id, host)
    ctl = located['ctl']
    if token != _token(ctl):
        raise WriteError('資料已被其他人改動，請重新預覽後再套用')

    result = preview(process_id, activity_id, items, host)
    if not result['changed_count']:
        return {'applied': False, 'reason': '沒有任何實際變更', 'backup_id': '',
                'changes': result['changes']}

    new_ctl = ctl
    for item in items:
        new_ctl = _edit(new_ctl, (item.get('id') or '').strip(),
                        (item.get('permission') or '').strip().upper())

    backup_id, backup_path = _backup(located['perm_oid'], ctl)

    bump_from = located['object_version'] if settings.BUMP_OBJECT_VERSION else None
    _update(located['perm_oid'], new_ctl, bump_from, host)

    # 寫後回讀：不一致就用備份還原，絕不假裝成功
    with service.connect(host) as database:
        after = database.query(READ_SQL, (located['perm_oid'],))[0]['ctl']
    if after != new_ctl:
        _update(located['perm_oid'], ctl, None, host)
        raise WriteError('寫入後回讀內容不一致，已用備份還原（備份 %s）' % backup_id)

    _audit({
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'actor': actor,
        'host': located['host'],
        'process_id': process_id,
        'activity_id': located['activity_id'],
        'perm_oid': located['perm_oid'],
        'backup_id': backup_id,
        'object_version_bumped': bool(bump_from),
        'changes': [c for c in result['changes'] if c['changed']],
    })

    cache.clear()      # 讓檢視器立刻反映新值
    return {'applied': True, 'reason': '', 'backup_id': backup_id,
            'backup_path': backup_path,
            'changes': [c for c in result['changes'] if c['changed']]}


# ---------------------------------------------------------------- 備份管理

def list_backups(limit=100):
    if not os.path.isdir(settings.BACKUP_DIR):
        return []
    names = sorted((n for n in os.listdir(settings.BACKUP_DIR) if n.endswith('.xml')),
                   reverse=True)
    entries = []
    for name in names[:limit]:
        path = os.path.join(settings.BACKUP_DIR, name)
        backup_id = name[:-4]
        entries.append({
            'backup_id': backup_id,
            'perm_oid': backup_id.split('_')[0],
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S',
                                        time.localtime(os.path.getmtime(path))),
            'size': os.path.getsize(path),
        })
    return entries


def restore(backup_id, host=None):
    """由備份還原。還原後同樣回讀比對。"""
    if not settings.ENABLE_WRITE:
        raise WriteError('寫入功能未啟用')
    entry = settings.host_entry(host or settings.DEFAULT_HOST)
    if not settings.host_writable(entry[0]):
        raise WriteError('主機 %s（%s）不允許寫入' % (entry[1], entry[2]))
    path = os.path.join(settings.BACKUP_DIR, backup_id + '.xml')
    if not os.path.isfile(path):
        raise WriteError('找不到備份 %s' % backup_id)
    perm_oid = backup_id.split('_')[0]

    with io.open(path, encoding='utf-8', newline='') as fh:
        original = fh.read()

    with service.connect(host) as database:
        shared = database.scalar(SHARE_SQL, (perm_oid,))
    if shared != 1:
        raise WriteError('這筆權限定義被 %d 個關卡共用，拒絕還原' % shared)

    _update(perm_oid, original, None, host)
    with service.connect(host) as database:
        after = database.query(READ_SQL, (perm_oid,))[0]['ctl']
    if after != original:
        raise WriteError('還原後回讀內容不一致')

    _audit({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'action': 'restore',
            'host': entry[0], 'perm_oid': perm_oid, 'backup_id': backup_id})
    cache.clear()
    return {'restored': True, 'backup_id': backup_id, 'perm_oid': perm_oid}
