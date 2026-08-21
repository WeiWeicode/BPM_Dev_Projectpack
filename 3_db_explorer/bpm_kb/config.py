# -*- coding: utf-8 -*-
"""連線設定：從 .env 或環境變數讀取，不在程式碼內留任何帳密。"""

import io
import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PACKAGE_DIR)          # 3_db_explorer
REPO_ROOT = os.path.dirname(BASE_DIR)

# 1_xml_tool 內的 core 套件負責解析 .form / .bpmn，本專案直接沿用
XML_TOOL_DIR = os.path.join(REPO_ROOT, '1_xml_tool')

# .env 放專案內或 repo 根目錄都能被找到
ENV_CANDIDATES = [os.path.join(BASE_DIR, '.env'), os.path.join(REPO_ROOT, '.env')]
ENV_PATH = ENV_CANDIDATES[0]

OUT_DIR = os.path.join(BASE_DIR, 'out')
FORM_DIR = os.path.join(OUT_DIR, 'forms')
PROCESS_DIR = os.path.join(OUT_DIR, 'processes')
DOC_DIR = os.path.join(BASE_DIR, 'docs')
SCHEMA_DIR = os.path.join(DOC_DIR, 'schema')

DEFAULTS = {
    'BPM_DB_HOST': '10.10.130.191',
    'BPM_DB_PORT': '1433',
    'BPM_DB_NAME': 'NaNa',
    'BPM_DB_USER': '',
    'BPM_DB_PASSWORD': '',
    'BPM_DB_DRIVER': '',
    'BPM_DB_TRUST_CERT': 'yes',
    'BPM_DB_TIMEOUT': '15',
}

# 依偏好順序挑選 ODBC 驅動
DRIVER_PREFERENCE = [
    'ODBC Driver 18 for SQL Server',
    'ODBC Driver 17 for SQL Server',
    'SQL Server Native Client 11.0',
    'SQL Server',
]


class ConfigError(Exception):
    """設定缺漏或無法建立連線字串。"""


def _load_env_file(path=None):
    """讀取 .env（KEY=VALUE，# 為註解），不覆寫既有的環境變數。"""
    values = {}
    candidates = [path] if path else ENV_CANDIDATES
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if path is None:
        return values
    with io.open(path, encoding='utf-8-sig') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load():
    """回傳合併後的設定：環境變數 > .env > 預設值。"""
    file_values = _load_env_file()
    settings = {}
    for key, fallback in DEFAULTS.items():
        settings[key] = os.environ.get(key) or file_values.get(key) or fallback
    return settings


def pick_driver(preferred=''):
    """挑一個系統上實際安裝的 SQL Server ODBC 驅動。"""
    try:
        import pyodbc
    except ImportError:
        raise ConfigError('尚未安裝 pyodbc，請執行：pip install -r requirements.txt')
    installed = pyodbc.drivers()
    if preferred:
        if preferred not in installed:
            raise ConfigError('指定的驅動不存在：%s（可用：%s）'
                              % (preferred, '、'.join(installed)))
        return preferred
    for name in DRIVER_PREFERENCE:
        if name in installed:
            return name
    raise ConfigError('找不到任何 SQL Server ODBC 驅動，請安裝 ODBC Driver 18 for SQL Server')


def connection_string(settings=None):
    """組出 pyodbc 連線字串；密碼未填時直接報錯提醒。"""
    settings = settings or load()
    if not settings['BPM_DB_USER'] or not settings['BPM_DB_PASSWORD']:
        raise ConfigError('缺少帳號或密碼，請複製 .env.example 為 .env 並填入 '
                          'BPM_DB_USER / BPM_DB_PASSWORD')
    driver = pick_driver(settings['BPM_DB_DRIVER'])
    parts = [
        'DRIVER={%s}' % driver,
        'SERVER=%s,%s' % (settings['BPM_DB_HOST'], settings['BPM_DB_PORT']),
        'DATABASE=%s' % settings['BPM_DB_NAME'],
        'UID=%s' % settings['BPM_DB_USER'],
        'PWD=%s' % settings['BPM_DB_PASSWORD'],
    ]
    if settings['BPM_DB_TRUST_CERT'].lower() in ('yes', 'true', '1'):
        parts.append('TrustServerCertificate=yes')
    parts.append('Encrypt=%s' % ('no' if driver == 'SQL Server' else 'yes'))
    return ';'.join(parts) + ';'


def describe(settings=None):
    """給人看的連線摘要，永遠不含密碼。"""
    settings = settings or load()
    return '%s@%s,%s/%s' % (settings['BPM_DB_USER'] or '(未設定)',
                            settings['BPM_DB_HOST'], settings['BPM_DB_PORT'],
                            settings['BPM_DB_NAME'])


def ensure_dirs():
    for path in (OUT_DIR, FORM_DIR, PROCESS_DIR, DOC_DIR, SCHEMA_DIR):
        if not os.path.isdir(path):
            os.makedirs(path)
