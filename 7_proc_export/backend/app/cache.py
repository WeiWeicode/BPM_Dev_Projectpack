# -*- coding: utf-8 -*-
"""記憶體 TTL 快取。

流程清單要 GROUP BY 55 萬列（實測 1.7 秒），表單定義要解析 XML；
兩者都不該每次請求重算。唯讀資料、單一 process，一個 dict 就夠。
"""

import threading
import time

from . import settings

_lock = threading.Lock()
_store = {}


def get_or_set(key, producer, ttl=None):
    """key 命中且未過期就回快取，否則呼叫 producer 並存起來。"""
    ttl = settings.CACHE_TTL if ttl is None else ttl
    now = time.time()
    with _lock:
        entry = _store.get(key)
        if entry is not None and entry[0] > now:
            return entry[1]

    # producer 在鎖外執行，避免一個慢查詢卡住所有請求
    value = producer()
    with _lock:
        _store[key] = (now + ttl, value)
    return value


def clear():
    with _lock:
        _store.clear()
