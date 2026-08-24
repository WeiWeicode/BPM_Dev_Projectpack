# -*- coding: utf-8 -*-
"""5_ws_explorer 後端設定與路徑管理。"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)  # 5_ws_explorer
FRONTEND_DIST = os.path.join(PROJECT_DIR, 'frontend', 'dist')

# 讓後端能直接引用 5_ws_explorer 根目錄下的 ws_client.py
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# 檔案路徑
API_JSON_PATH = os.path.join(PROJECT_DIR, 'out', 'WorkflowServiceService.json')
PROBE_JSON_PATH = os.path.join(PROJECT_DIR, 'out', 'probe_result.json')
WRITE_PROBE_JSON_PATH = os.path.join(PROJECT_DIR, 'out', 'write_probe_result.json')
NOTES_JSON_PATH = os.path.join(PROJECT_DIR, 'notes.json')
SEEDS_JSON_PATH = os.path.join(PROJECT_DIR, 'seeds.json')
PAYLOAD_DIR = os.path.join(PROJECT_DIR, 'out', 'payloads')
MANUAL_MD_PATH = os.path.join(PROJECT_DIR, 'docs', 'WorkflowService_API手冊.md')

# 預設 Endpoint（191 測試區）
DEFAULT_ENDPOINT = 'http://10.10.130.191:8080/NaNaWeb/services/WorkflowService'

# CORS 來源
DEV_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
]
