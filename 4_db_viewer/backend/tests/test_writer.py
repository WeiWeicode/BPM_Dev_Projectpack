# -*- coding: utf-8 -*-
"""寫入引擎測試。

字串編輯與防護邏輯不需要資料庫，一律執行。
真的會寫資料庫的整合測試預設**跳過**，要跑必須同時設：

    BPM_VIEWER_ENABLE_WRITE=1
    BPM_VIEWER_WRITABLE_PROCESSES=quickDevTestProcessImportWebTool
    BPM_VIEWER_WRITE_TEST=1

三個都設齊才會動手 —— 不會有人不小心跑到。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import cache, settings, writer  # noqa: E402

CTL = ('<FormFieldAccessControl><quickDevTestFormImport>'
       '<TEST_Button_06>ENABLED</TEST_Button_06>'
       '<TEST_TextBox_07>ENABLED</TEST_TextBox_07>'
       '<TEST_Grid_10>INVISIBLE</TEST_Grid_10>'
       '</quickDevTestFormImport></FormFieldAccessControl>')


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------- 讀出目前值

def test_current_reads_stored_value():
    assert writer._current(CTL, 'TEST_Grid_10') == 'INVISIBLE'


def test_current_of_unlisted_is_disable():
    """未列出 = 唯讀(Disable)，這是對照 BPM 設計師 UI 確認的。"""
    assert writer._current(CTL, 'TEST_Date_19') == 'DISABLE'


# ---------------------------------------------------------------- 字串編輯

def test_edit_replaces_value_in_place():
    result = writer._edit(CTL, 'TEST_Button_06', 'INVISIBLE')
    assert '<TEST_Button_06>INVISIBLE</TEST_Button_06>' in result
    # 其他元件一個位元組都不能動
    assert '<TEST_TextBox_07>ENABLED</TEST_TextBox_07>' in result
    assert '<TEST_Grid_10>INVISIBLE</TEST_Grid_10>' in result


def test_edit_disable_removes_the_tag():
    """設成唯讀就是把標籤移除，不是寫入某個值。"""
    result = writer._edit(CTL, 'TEST_Button_06', 'DISABLE')
    assert 'TEST_Button_06' not in result
    assert writer._current(result, 'TEST_Button_06') == 'DISABLE'


def test_edit_disable_on_absent_field_is_noop():
    assert writer._edit(CTL, 'TEST_Date_19', 'DISABLE') == CTL


def test_edit_inserts_before_closing_form_tag():
    """原本唯讀的元件要給權限 -> 插在表單區塊結尾前。"""
    result = writer._edit(CTL, 'TEST_Date_19', 'ENABLED')
    assert '<TEST_Date_19>ENABLED</TEST_Date_19></quickDevTestFormImport>' in result
    assert result.endswith('</FormFieldAccessControl>')


def test_edit_only_touches_target():
    """替換前後長度差 = 值的長度差，證明沒有動到別處。"""
    result = writer._edit(CTL, 'TEST_Button_06', 'INVISIBLE')
    assert len(result) - len(CTL) == len('INVISIBLE') - len('ENABLED')


def test_edit_round_trip_restores_bytes():
    changed = writer._edit(CTL, 'TEST_Button_06', 'INVISIBLE')
    assert writer._edit(changed, 'TEST_Button_06', 'ENABLED') == CTL


# ---------------------------------------------------------------- token

def test_token_changes_with_content():
    assert writer._token(CTL) != writer._token(CTL + ' ')


def test_token_is_stable():
    assert writer._token(CTL) == writer._token(CTL)


# ---------------------------------------------------------------- 防護

def test_write_disabled_by_default():
    """預設不開寫入 —— 這個測試若失敗代表有人動了預設值。"""
    if os.environ.get('BPM_VIEWER_ENABLE_WRITE'):
        pytest.skip('本次執行刻意開啟了寫入旗標')
    assert settings.ENABLE_WRITE is False


def test_locate_rejects_when_write_disabled(monkeypatch):
    monkeypatch.setattr(settings, 'ENABLE_WRITE', False)
    with pytest.raises(writer.WriteError, match='未啟用'):
        writer._locate('any', 'any')


def test_locate_rejects_process_outside_whitelist(monkeypatch):
    monkeypatch.setattr(settings, 'ENABLE_WRITE', True)
    monkeypatch.setattr(settings, 'WRITABLE_PROCESSES', ('allowed_only',))
    with pytest.raises(writer.WriteError, match='白名單'):
        writer._locate('some_other_process', 'ACT_1')


def test_allowed_values_exclude_invalidity():
    """INVALIDITY 在 20000 筆取樣中從未出現，格式未知，不可支援。"""
    assert 'INVALIDITY' not in writer.ALLOWED_VALUES
    assert writer.ALLOWED_VALUES == ('ENABLED', 'INVISIBLE', 'FULL_CONTROL', 'DISABLE')


def test_preview_rejects_unknown_permission(monkeypatch):
    monkeypatch.setattr(writer, '_locate',
                        lambda p, a: {'process_id': p, 'activity_id': a,
                                      'activity_name': '', 'perm_oid': 'x',
                                      'ctl': CTL, 'object_version': 1})
    with pytest.raises(writer.WriteError, match='不支援的權限值'):
        writer.preview('p', 'a', [{'id': 'TEST_Button_06', 'permission': 'READ_ONLY'}])


# ---------------------------------------------------------------- 整合（真的會寫）

WRITE_TEST_READY = (
    os.environ.get('BPM_VIEWER_WRITE_TEST') == '1'
    and settings.ENABLE_WRITE
    and 'quickDevTestProcessImportWebTool' in settings.WRITABLE_PROCESSES
)

PROCESS_ID = 'quickDevTestProcessImportWebTool'
ACTIVITY_ID = 'ACT_ManagerApprove_02'


@pytest.mark.skipif(not WRITE_TEST_READY,
                    reason='未設定 BPM_VIEWER_WRITE_TEST=1 等三個環境變數，跳過真實寫入')
def test_apply_then_restore_round_trip():
    """套用後再由備份還原，內容必須回到原樣。"""
    before = writer._locate(PROCESS_ID, ACTIVITY_ID)['ctl']

    items = [{'id': 'TEST_Button_06', 'permission': 'INVISIBLE'}]
    token = writer.preview(PROCESS_ID, ACTIVITY_ID, items)['token']
    result = writer.apply(PROCESS_ID, ACTIVITY_ID, items, token, actor='pytest')
    assert result['applied'] is True
    assert result['backup_id']

    after = writer._locate(PROCESS_ID, ACTIVITY_ID)['ctl']
    assert '<TEST_Button_06>INVISIBLE</TEST_Button_06>' in after

    writer.restore(result['backup_id'])
    restored = writer._locate(PROCESS_ID, ACTIVITY_ID)['ctl']
    assert restored == before


@pytest.mark.skipif(not WRITE_TEST_READY,
                    reason='未設定 BPM_VIEWER_WRITE_TEST=1 等三個環境變數，跳過真實寫入')
def test_stale_token_is_rejected():
    items = [{'id': 'TEST_Button_06', 'permission': 'INVISIBLE'}]
    with pytest.raises(writer.WriteError, match='已被其他人改動'):
        writer.apply(PROCESS_ID, ACTIVITY_ID, items, 'stale-token')
