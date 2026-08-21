# -*- coding: utf-8 -*-
"""服務層測試。

純轉換邏輯不需要資料庫；需要連線的整合測試在連不上時跳過，
但**不會靜默通過** —— 跳過訊息會說明原因。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import cache, service  # noqa: E402
from app.settings import ensure_bpm_kb  # noqa: E402

ensure_bpm_kb()

from bpm_kb import process_graph  # noqa: E402


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------- 按鈕判定

def test_classify_uses_form_type_not_naming():
    """型別是 BUTTON 就算按鈕，即使 ID 完全看不出來。"""
    lookup = {'TEST_Confirm_09': {'name': '確認', 'type': 'BUTTON'}}
    item, is_button = process_graph._classify('TEST_Confirm_09', 'ENABLED', lookup)
    assert is_button is True
    assert item['name'] == '確認'
    assert item['orphaned'] is False


def test_classify_falls_back_to_naming_without_index():
    """沒有表單索引時退回 ID 命名猜測（僅比對 _ 邊界，故意保守）。"""
    item, is_button = process_graph._classify('btn_save', 'ENABLED', {})
    assert is_button is True
    assert item['name'] == ''
    assert item['orphaned'] is False


def test_naming_fallback_misses_camel_case():
    """SubmitBtn 這種沒有底線邊界的命名猜不到 —— 正是要靠型別 join 的原因。"""
    _item, is_button = process_graph._classify('SubmitBtn', 'ENABLED', {})
    assert is_button is False


def test_classify_marks_orphaned():
    """權限有、表單定義沒有 —— 必須標出來，不可靜默忽略。"""
    lookup = {'TEST_TextBox_07': {'name': '輸入框', 'type': 'TEXTBOX'}}
    item, _ = process_graph._classify('TEST_Removed_99', 'INVISIBLE', lookup)
    assert item['orphaned'] is True


def test_non_button_field_stays_field():
    lookup = {'TEST_TextBox_07': {'name': '輸入框', 'type': 'TEXTBOX'}}
    item, is_button = process_graph._classify('TEST_TextBox_07', 'ENABLED', lookup)
    assert is_button is False
    assert item['type'] == 'TEXTBOX'


# ---------------------------------------------------------------- 分頁與篩選

def test_page_clamps_limit():
    items = list(range(500))
    page, total = service._page(items, 10, 0)
    assert len(page) == 10 and total == 500


def test_page_rejects_oversized_limit():
    items = list(range(5000))
    page, _ = service._page(items, 99999, 0)
    assert len(page) == service.settings.MAX_LIMIT


def test_match_is_case_insensitive():
    row = {'id': 'quickDevTestForm', 'formDefinitionName': '快速開發測試'}
    assert service._match(row, 'quickdev', ('id', 'formDefinitionName'))
    assert service._match(row, '快速', ('id', 'formDefinitionName'))
    assert not service._match(row, '不存在', ('id', 'formDefinitionName'))


# ---------------------------------------------------------------- 矩陣組裝

FORM_INDEX = {'F1': {'Btn': {'name': '送出', 'type': 'BUTTON'},
                     'Txt': {'name': '輸入框', 'type': 'TEXTBOX'}}}


def _fake_detail(empty_first=False):
    """A0 沒掛表單；A1 開單；A2 主管。empty_first 模擬「開單全設唯讀」。"""
    return {
        'process_id': 'P1', 'process_name': '測試流程', 'version': 2,
        'activities': [
            {'id': 'A0', 'name': '起點', 'form_id': '', 'buttons': [], 'fields': []},
            {'id': 'A1', 'name': '開單', 'form_id': 'F1',
             'buttons': [] if empty_first else [
                 {'id': 'Btn', 'name': '送出', 'type': 'BUTTON',
                  'permission': 'ENABLED', 'orphaned': False}],
             'fields': [] if empty_first else [
                 {'id': 'Txt', 'name': '輸入框', 'type': 'TEXTBOX',
                  'permission': 'ENABLED', 'orphaned': False}]},
            {'id': 'A2', 'name': '主管', 'form_id': 'F1',
             'buttons': [],
             'fields': [{'id': 'Txt', 'name': '輸入框', 'type': 'TEXTBOX',
                         'permission': 'INVISIBLE', 'orphaned': False}]},
        ],
    }


def _patch(monkeypatch, empty_first=False):
    monkeypatch.setattr(service, 'get_process', lambda pid: _fake_detail(empty_first))
    monkeypatch.setattr(service, '_form_indexes', lambda ids: FORM_INDEX)


def test_matrix_excludes_activities_without_a_form(monkeypatch):
    """沒掛表單的關卡（如起點、通知任務）不該出現在矩陣。"""
    _patch(monkeypatch)
    assert [c['id'] for c in service.get_matrix('P1')['columns']] == ['A1', 'A2']


def test_matrix_keeps_activity_with_no_permissions_set(monkeypatch):
    """迴歸：關卡全設唯讀後權限清單為空，仍必須留在矩陣中，否則改不回來。"""
    _patch(monkeypatch, empty_first=True)
    matrix = service.get_matrix('P1')
    assert [c['id'] for c in matrix['columns']] == ['A1', 'A2']
    row = next(r for r in matrix['rows'] if r['id'] == 'Btn')
    assert row['cells'][0]['permission'] is None       # 開單 = 唯讀
    assert row['cells'][0]['applicable'] is True       # 但仍可編輯


def test_matrix_rows_come_from_form_definition(monkeypatch):
    """列以表單定義為準，沒設過權限的元件也要看得到。"""
    _patch(monkeypatch, empty_first=True)
    rows = {r['id'] for r in service.get_matrix('P1')['rows']}
    assert rows == {'Btn', 'Txt'}


def test_matrix_cells_align_with_columns(monkeypatch):
    _patch(monkeypatch)
    matrix = service.get_matrix('P1')
    row = next(r for r in matrix['rows'] if r['id'] == 'Txt')
    assert [c['permission'] for c in row['cells']] == ['ENABLED', 'INVISIBLE']
    button = next(r for r in matrix['rows'] if r['id'] == 'Btn')
    assert button['is_button'] is True
    # A2 沒設定這個按鈕 -> None，代表未列出，也就是唯讀(Disable)
    assert [c['permission'] for c in button['cells']] == ['ENABLED', None]


def test_matrix_only_button_filter(monkeypatch):
    _patch(monkeypatch)
    assert [r['id'] for r in service.get_matrix('P1', 'button')['rows']] == ['Btn']
    assert [r['id'] for r in service.get_matrix('P1', 'field')['rows']] == ['Txt']


# ---------------------------------------------------------------- 快取

def test_cache_returns_same_value_and_counts():
    calls = []

    def producer():
        calls.append(1)
        return 'v'

    assert cache.get_or_set('k', producer) == 'v'
    assert cache.get_or_set('k', producer) == 'v'
    assert len(calls) == 1
    assert cache.stats()['hit'] == 1


# ---------------------------------------------------------------- 整合（需連線）

def _db_available():
    return service.health().get('ok') is True


@pytest.mark.skipif(not _db_available(),
                    reason='無法連線到 BPM 資料庫，跳過整合測試（非通過，是跳過）')
def test_only_released_versions_are_returned():
    forms, _ = service.list_forms(limit=1000)
    processes, _ = service.list_processes(limit=1000)
    assert forms and processes
    with service.Database() as database:
        all_forms = service.extract.list_forms(database, latest_only=True)
    released_ids = {f['form_id'] for f in forms}
    revision_only = {(r['id'] or '').strip() for r in all_forms
                     if (r.get('publicationStatus') or '').strip() == 'UNDER_REVISION'}
    # 只有修訂中版本的表單不該出現在 API 回應
    assert not (released_ids & (revision_only - released_ids))
