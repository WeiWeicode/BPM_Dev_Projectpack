# -*- coding: utf-8 -*-
"""資料庫連線：唯讀，可在測試區與正式區之間切換。

主機由每個請求的 host 參數決定，不存伺服器端狀態。
連線一律經由 bpm_kb.db.Database（readonly=True），本專案不寫任何寫入路徑。
"""

import os

from . import settings

settings.ensure_bpm_kb()

from bpm_kb import config  # noqa: E402
from bpm_kb.db import Database  # noqa: E402


def db_settings(host=None):
    """把 .env 的設定套上指定主機的位址與（選填的）專屬帳密。

    兩區帳密相同時什麼都不用設；不同時用 BPM_DB_USER_190 這類環境變數覆寫。
    """
    entry = settings.host_entry(host or settings.DEFAULT_HOST)
    values = dict(config.load())
    values['BPM_DB_HOST'] = entry[2]
    for field in ('BPM_DB_USER', 'BPM_DB_PASSWORD', 'BPM_DB_NAME'):
        override = os.environ.get('%s_%s' % (field, entry[0]))
        if override:
            values[field] = override
    return values


def connect(host=None):
    return Database(db_settings(host))


def cache_key(host, name):
    """快取 key 一律帶主機，避免兩台的資料互相污染。"""
    return '%s:%s' % (host or settings.DEFAULT_HOST, name)


def host_list():
    return [{'key': key, 'label': label, 'address': address, 'production': production}
            for key, label, address, production in settings.HOSTS]


def describe(host=None):
    """給人看的連線摘要：只有主機與資料庫。

    刻意不含帳號 —— 這串會被寫進交給稽核的 Excel，
    帳號名稱沒有必要跟著流出去（密碼本來就不會出現在這裡）。
    """
    values = db_settings(host)
    return '%s,%s/%s' % (values['BPM_DB_HOST'], values['BPM_DB_PORT'],
                         values['BPM_DB_NAME'])
