# -*- coding: utf-8 -*-
"""鼎新 BPM 資料庫知識萃取模組。

config  連線設定（.env）
db      SQL Server 唯讀查詢封裝
probe   資料表／欄位探索，找出定義 XML 的存放位置
extract 表單與流程定義萃取，落地成 .form / .bpmn
process_graph  從關聯表把流程邏輯組回完整結構
digest  產生 docs/BPM_知識重點.md
"""

from . import config, db, probe, extract, process_graph, digest  # noqa: F401

__all__ = ['config', 'db', 'probe', 'extract', 'process_graph', 'digest']
