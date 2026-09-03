# -*- coding: utf-8 -*-
"""路徑解析、可切換主機與匯出上限。

與 4_db_viewer 一樣不重寫任何查詢，直接沿用 3_db_explorer 的 bpm_kb；
這裡負責把它的路徑加進 sys.path。

主機清單刻意與 4_db_viewer 保持同樣的格式與環境變數命名，
兩個工具切換環境的心智模型才不會分岔。
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)          # 7_proc_export
REPO_ROOT = os.path.dirname(PROJECT_DIR)
DB_EXPLORER_DIR = os.path.join(REPO_ROOT, '3_db_explorer')
FRONTEND_DIST = os.path.join(PROJECT_DIR, 'frontend', 'dist')

# 流程清單與表單定義都不會分秒變動，快取住；要立即更新就重啟服務
CACHE_TTL = int(os.environ.get('BPM_EXPORT_CACHE_TTL') or 600)

DEV_ORIGINS = ['http://localhost:5176', 'http://127.0.0.1:5176']

# ---------------------------------------------------------------- 資料庫主機
# 格式：key|標籤|位址|是否正式區，多筆以逗號分隔，用 BPM_EXPORT_HOSTS 覆寫。
# 兩區帳密相同時不必另設；不同時用 BPM_DB_USER_190 / BPM_DB_PASSWORD_190 覆寫。
DEFAULT_HOSTS = [
    ('191', 'BPM 191 測試區', '10.10.130.191', False),
    ('190', 'BPM 190 正式區', '10.10.130.190', True),
]


def _parse_hosts():
    raw = os.environ.get('BPM_EXPORT_HOSTS') or ''
    if not raw:
        return list(DEFAULT_HOSTS)
    hosts = []
    for chunk in raw.split(','):
        parts = [p.strip() for p in chunk.split('|')]
        if len(parts) < 3 or not parts[0]:
            continue
        production = len(parts) > 3 and parts[3].lower() in ('1', 'true', 'yes')
        hosts.append((parts[0], parts[1] or parts[0], parts[2], production))
    return hosts or list(DEFAULT_HOSTS)


HOSTS = _parse_hosts()
HOST_KEYS = tuple(h[0] for h in HOSTS)
DEFAULT_HOST = os.environ.get('BPM_EXPORT_DEFAULT_HOST') or (HOST_KEYS[0] if HOST_KEYS else '')


def host_entry(key):
    """回傳 (key, 標籤, 位址, 是否正式區)；找不到就用預設主機。"""
    for entry in HOSTS:
        if entry[0] == key:
            return entry
    for entry in HOSTS:
        if entry[0] == DEFAULT_HOST:
            return entry
    return HOSTS[0]


# ---------------------------------------------------------------- 查詢與匯出上限
# 匯出上限存在的理由不是保護資料庫（查詢本身很快），而是保護產出：
# 逐欄展開後一列可能上百欄，兩萬列已經是開得起來的 Excel 的上限附近。
MAX_EXPORT_ROWS = int(os.environ.get('BPM_EXPORT_MAX_ROWS') or 20000)

# 畫面上的分頁
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

# 建立可選欄位清單時，抽幾張實際單據補上表單定義裡沒有的欄位
FIELD_SAMPLE_ROWS = int(os.environ.get('BPM_EXPORT_FIELD_SAMPLE') or 200)

# 自訂欄位的篩選在 Python 端做（fieldValues 是 ntext，SQL LIKE 會全表掃描），
# 因此先用「流程 + 日期」把候選壓到這個數量以內才開始逐張解析。
MAX_SCAN_ROWS = int(os.environ.get('BPM_EXPORT_MAX_SCAN') or 50000)


def ensure_bpm_kb():
    """讓 bpm_kb 可被 import；重複呼叫安全。"""
    if DB_EXPLORER_DIR not in sys.path:
        sys.path.insert(0, DB_EXPLORER_DIR)


ensure_bpm_kb()
