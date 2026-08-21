# -*- coding: utf-8 -*-
"""路徑解析與執行參數。

本專案不重寫任何資料庫查詢，而是直接沿用 3_db_explorer 的 bpm_kb 模組；
這裡負責把它的路徑加進 sys.path，做法與 bpm_kb 引用 1_xml_tool/core 一致。
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)          # 4_db_viewer
REPO_ROOT = os.path.dirname(PROJECT_DIR)
DB_EXPLORER_DIR = os.path.join(REPO_ROOT, '3_db_explorer')
FRONTEND_DIST = os.path.join(PROJECT_DIR, 'frontend', 'dist')

# 快取存活秒數；結構不會分秒變動，需要立即更新就重啟服務
CACHE_TTL = int(os.environ.get('BPM_VIEWER_CACHE_TTL') or 600)

# 清單端點的預設與最大筆數
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000

# 開發時 Vite dev server 的來源，正式部署由後端直接吐靜態檔不需要 CORS
DEV_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173']

# ---------------------------------------------------------------- 寫入功能
# 預設關閉。沒開時連寫入路由都不會註冊，不是靠檢查擋。
ENABLE_WRITE = (os.environ.get('BPM_VIEWER_ENABLE_WRITE') or '').lower() \
    in ('1', 'true', 'yes')

# 可寫入的流程 ID 白名單（逗號分隔）。空值代表全部禁止 —— 開了旗標也不會誤傷。
WRITABLE_PROCESSES = tuple(
    p.strip() for p in (os.environ.get('BPM_VIEWER_WRITABLE_PROCESSES') or '').split(',')
    if p.strip())

# 是否連帶遞增 objectVersion。實測未驗證其影響，故預設不動 ——
# 我們唯一驗證過的組合是「不動 objectVersion」，設計師能正常讀到改動。
BUMP_OBJECT_VERSION = (os.environ.get('BPM_VIEWER_BUMP_OBJECT_VERSION') or '').lower() \
    in ('1', 'true', 'yes')

BACKUP_DIR = os.path.join(BACKEND_DIR, 'backups')
AUDIT_LOG = os.path.join(BACKUP_DIR, 'audit.log')


def ensure_bpm_kb():
    """讓 bpm_kb 可被 import；重複呼叫安全。"""
    if DB_EXPLORER_DIR not in sys.path:
        sys.path.insert(0, DB_EXPLORER_DIR)


ensure_bpm_kb()
