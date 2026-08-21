# -*- coding: utf-8 -*-
"""SQL Server 連線與查詢封裝。

一律唯讀使用：對外只提供 SELECT 導向的 helper，並在 CLI 層擋掉非 SELECT 語句。
ntext / image 這類舊型別在 pyodbc 需要轉型，故查大欄位時統一 CAST 成 nvarchar(max)。
"""

from . import config

_pyodbc = None


def _driver():
    global _pyodbc
    if _pyodbc is None:
        try:
            import pyodbc
        except ImportError:
            raise config.ConfigError('尚未安裝 pyodbc，請執行：pip install -r requirements.txt')
        _pyodbc = pyodbc
    return _pyodbc


class Database(object):
    """一次連線、多次查詢；建議以 with 使用。"""

    def __init__(self, settings=None):
        self.settings = settings or config.load()
        self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def connect(self):
        if self._conn is not None:
            return self._conn
        pyodbc = _driver()
        cs = config.connection_string(self.settings)
        timeout = int(self.settings.get('BPM_DB_TIMEOUT') or 15)
        try:
            self._conn = pyodbc.connect(cs, timeout=timeout, readonly=True)
        except pyodbc.Error as exc:
            raise config.ConfigError('連線失敗（%s）：%s'
                                     % (config.describe(self.settings), exc.args[-1]))
        return self._conn

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def query(self, sql, params=()):
        """執行查詢並回傳 list[dict]。"""
        cursor = self.connect().cursor()
        try:
            cursor.execute(sql, params) if params else cursor.execute(sql)
            if cursor.description is None:
                return []
            columns = [c[0] for c in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def scalar(self, sql, params=()):
        rows = self.query(sql, params)
        if not rows:
            return None
        return list(rows[0].values())[0]

    def table_exists(self, name):
        return bool(self.scalar(
            "SELECT 1 FROM sys.tables WHERE name = ?", (name,)))


def big_text(column):
    """把 ntext / text / nvarchar(max) 欄位轉成可安全讀取的表示式。"""
    return 'CAST(%s AS nvarchar(max))' % column
