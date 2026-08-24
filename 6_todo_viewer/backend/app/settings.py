# -*- coding: utf-8 -*-
"""路徑解析、主機清單與執行參數。

本專案不重寫資料庫連線，直接沿用 3_db_explorer 的 bpm_kb；
多主機切換的做法比照 4_db_viewer，差別是這裡多帶一個 web base ——
「前往 BPM」的深連結要跟著資料來源走，查哪一區就給哪一區的網址。
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)          # 6_todo_viewer
REPO_ROOT = os.path.dirname(PROJECT_DIR)
DB_EXPLORER_DIR = os.path.join(REPO_ROOT, '3_db_explorer')
FRONTEND_DIST = os.path.join(PROJECT_DIR, 'frontend', 'dist')

# 清單端點的預設與最大筆數。「我經辦過的」動輒數千筆，一律分頁
DEFAULT_LIMIT = 50
MAX_LIMIT = 500

# 開發時 Vite dev server 的來源，正式部署由後端直接吐靜態檔不需要 CORS
DEV_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173']

# ---------------------------------------------------------------- 資料庫主機
# 格式：key|標籤|資料庫位址|是否正式區|BPM 網站位址
# 用 BPM_TODO_HOSTS 覆寫，多筆以逗號分隔
DEFAULT_HOSTS = [
    ('191', 'BPM 191 測試區', '10.10.130.191', False, 'http://10.10.130.191:8080'),
    ('190', 'BPM 190 正式區', '10.10.130.190', True, 'http://10.10.130.190:9090'),
]


def _parse_hosts():
    raw = os.environ.get('BPM_TODO_HOSTS') or ''
    if not raw:
        return list(DEFAULT_HOSTS)
    hosts = []
    for chunk in raw.split(','):
        parts = [p.strip() for p in chunk.split('|')]
        if len(parts) < 3 or not parts[0]:
            continue
        production = len(parts) > 3 and parts[3].lower() in ('1', 'true', 'yes')
        web_base = parts[4] if len(parts) > 4 else ''
        hosts.append((parts[0], parts[1] or parts[0], parts[2], production, web_base))
    return hosts or list(DEFAULT_HOSTS)


HOSTS = _parse_hosts()
HOST_KEYS = tuple(h[0] for h in HOSTS)
DEFAULT_HOST = os.environ.get('BPM_TODO_DEFAULT_HOST') or (HOST_KEYS[0] if HOST_KEYS else '')


def host_entry(key):
    """回傳 (key, 標籤, 資料庫位址, 是否正式區, 網站位址)；找不到就用預設主機。"""
    for entry in HOSTS:
        if entry[0] == key:
            return entry
    for entry in HOSTS:
        if entry[0] == DEFAULT_HOST:
            return entry
    return HOSTS[0]


def ensure_bpm_kb():
    """讓 bpm_kb 可被 import；重複呼叫安全。"""
    if DB_EXPLORER_DIR not in sys.path:
        sys.path.insert(0, DB_EXPLORER_DIR)


ensure_bpm_kb()
