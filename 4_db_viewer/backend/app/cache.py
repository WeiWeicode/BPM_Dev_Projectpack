# -*- coding: utf-8 -*-
"""記憶體 TTL 快取。

明細端點要撈並解析 200 KB 級的 XML，不能每次請求都做。
唯讀資料、單一 process，用一個 dict 就夠 —— 不引入 Redis 之類的東西。
"""

import threading
import time

from . import settings

_lock = threading.Lock()
_store = {}
_stats = {'hit': 0, 'miss': 0}


def get_or_set(key, producer, ttl=None):
    """key 命中且未過期就回快取，否則呼叫 producer 並存起來。"""
    ttl = settings.CACHE_TTL if ttl is None else ttl
    now = time.time()
    with _lock:
        entry = _store.get(key)
        if entry is not None and entry[0] > now:
            _stats['hit'] += 1
            return entry[1]
        _stats['miss'] += 1

    # producer 在鎖外執行，避免一個慢查詢卡住所有請求
    value = producer()
    with _lock:
        _store[key] = (now + ttl, value)
    return value


def stats():
    with _lock:
        return {'entries': len(_store), 'hit': _stats['hit'], 'miss': _stats['miss']}


def clear():
    """僅供測試使用；服務本身不提供清快取的端點。"""
    with _lock:
        _store.clear()
        _stats['hit'] = 0
        _stats['miss'] = 0
