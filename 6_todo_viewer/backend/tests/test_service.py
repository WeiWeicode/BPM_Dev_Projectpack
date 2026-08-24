# -*- coding: utf-8 -*-
"""服務層測試。

純轉換邏輯（XML 解析、深連結、狀態對照）不需要資料庫；
需要連線的整合測試在連不上時跳過，但**不會靜默通過** —— 跳過訊息會說明原因。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import service  # noqa: E402

# 取自 191 實測資料（SIC00500000027、VISOMod001_v200000007）的縮減樣本
SAMPLE_XML = '''
<MIS_Application>
<ddtype2 id="ddtype2" dataType="java.lang.String">ERP</ddtype2>
<sqrxm id="sqrxm" dataType="java.lang.String" perDataProId="">鄭智寬</sqrxm>
<chkfill id="chkfill" dataType="java.lang.String"></chkfill>
<Attachment id="Attachment">
<attachments>
<attachment OID="cb47a854f84310048892ddd85de7b00c" id="cb394db8.pdf" name="cb394db8.pdf"
 originalFileName="放行單.pdf" fileType="pdf" fileSize="93123"
 creatorName="曾月楦" activityName="發起人 確認">
<description></description>
</attachment>
</attachments>
</Attachment>
<Grid_Attachment id="Grid_Attachment">
<records>
<record id="Grid_Attachment_0">
<item id="docFileName" dataType="java.lang.String">cb394db8.pdf</item>
<item id="security" dataType="java.lang.String">高安全性</item>
</record>
</records>
</Grid_Attachment>
</MIS_Application>
'''


# ---------------------------------------------------------------- XML 解析

def test_parse_splits_fields_grids_attachments():
    fields, grids, attachments = service.parse_field_values(SAMPLE_XML)
    assert fields['ddtype2'] == 'ERP'
    assert fields['sqrxm'] == '鄭智寬'
    assert list(grids) == ['Grid_Attachment']
    assert grids['Grid_Attachment'][0]['security'] == '高安全性'
    assert attachments[0]['original_file_name'] == '放行單.pdf'
    assert attachments[0]['activity_name'] == '發起人 確認'


def test_parse_keeps_empty_field_as_empty_string():
    """空值欄位要留著並顯示為空 —— 不是「這張單沒有這個欄位」。"""
    fields, _grids, _att = service.parse_field_values(SAMPLE_XML)
    assert fields['chkfill'] == ''


def test_parse_excludes_grid_and_attachment_from_plain_fields():
    fields, _grids, _att = service.parse_field_values(SAMPLE_XML)
    assert 'Grid_Attachment' not in fields
    assert 'Attachment' not in fields


def test_parse_raises_on_broken_xml():
    """壞掉的 XML 要往外拋，由端點轉成 form_parse_error，不能吞掉。"""
    import xml.etree.ElementTree as ET
    with pytest.raises(ET.ParseError):
        service.parse_field_values('<a><b></a>')


# ---------------------------------------------------------------- 深連結

def test_perform_url_matches_mail_format():
    url = service.perform_url('190', 'GV112001', 'b16ac18cf9241004822a71e095b2d9c2')
    assert url == ('http://10.10.130.190:9090/NaNaWeb/GP/PerformWorkFromMail'
                   '?hdnMethod=performWorkFromMail&hdnUserId=GV112001'
                   '&hdnWorkItemOID=b16ac18cf9241004822a71e095b2d9c2')


def test_perform_url_follows_data_source():
    """查哪一區的資料就給哪一區的連結。"""
    assert service.perform_url('191', 'S094009', 'abc').startswith('http://10.10.130.191:8080')


def test_trace_url_matches_notification_mail_format():
    """格式取自 BPM 自己寄的通知信（ProcessNotification.message）。"""
    url = service.trace_url('190', 'S098007', 'dec695fff087100482e36ec59553a249')
    assert url == ('http://10.10.130.190:9090/NaNaWeb/GP/WMS/TraceProcess/TraceProcessMain'
                   '?hdnMethod=traceProcessFromMail&hdnCurrentUserId=S098007'
                   '&hdnProcessInstOID=dec695fff087100482e36ec59553a249')


def test_trace_url_empty_without_process_oid():
    assert service.trace_url('191', 'S094009', '') == ''


def test_perform_url_empty_without_work_item():
    """缺材料時回空字串，讓畫面顯示「無可用連結」，不給半條假網址。"""
    assert service.perform_url('191', 'S094009', '') == ''


# ---------------------------------------------------------------- 狀態對照

def test_process_state_label_known_values():
    assert service.process_state_label(1) == '進行中'
    assert service.process_state_label(3) == '已結案'


def test_process_state_label_marks_unknown():
    """沒見過的代碼要顯示原值，不能歸類成「其他」就把資訊丟掉。"""
    assert service.process_state_label(42) == '其他(42)'


def test_todo_states_exclude_abnormal():
    """97 不算待辦 —— 依 docs/待辦狀態語意.md 的 SOAP 交叉驗證結果。"""
    assert service.TODO_STATES == (0, 1)
    assert service.ABNORMAL_STATE not in service.TODO_STATES


# ---------------------------------------------------------------- 整合（需連線）

@pytest.fixture(scope='module')
def live_db():
    try:
        with service.connect('191') as database:
            database.scalar('SELECT 1')
    except Exception as exc:
        pytest.skip('連不上 191 測試區，略過整合測試：%s' % exc)
    return '191'


def test_search_users_returns_all_accounts(live_db):
    """同一個人的多個公司別帳號都要回，不能只回第一筆。"""
    rows = service.search_users('蔣佳緯', live_db)
    ids = {r['id'] for r in rows}
    assert {'GV112001', 'S112009'} <= ids


def test_todo_matches_soap_verified_count(live_db):
    """S094009 的待辦數應為 8，另有 2 筆 97 異常 —— 見 docs/待辦狀態語意.md。"""
    user = service.get_user('S094009', live_db)
    result = service.list_todo(user, live_db)
    assert result['total'] == 8
    assert result['abnormal_total'] == 2
    assert all(item['perform_url'] for item in result['items'])


def test_requested_and_handled_are_paged(live_db):
    user = service.get_user('S094009', live_db)
    requested = service.list_requested(user, live_db, limit=5)
    handled = service.list_handled(user, live_db, limit=5)
    assert requested['total'] > len(requested['items']) == 5
    assert handled['total'] > len(handled['items']) == 5


def test_requested_and_handled_carry_trace_url(live_db):
    """這兩類單沒有可簽核的工作項目，但都連得到流程追蹤畫面。"""
    user = service.get_user('S094009', live_db)
    for result in (service.list_requested(user, live_db, limit=5),
                   service.list_handled(user, live_db, limit=5)):
        assert result['items']
        for item in result['items']:
            assert 'TraceProcessMain' in item['trace_url']
            assert 'hdnCurrentUserId=S094009' in item['trace_url']


def test_trace_oid_is_process_instance_oid_not_context_oid(live_db):
    """迴歸測試：通知信用的是 ProcessInstance.OID，接成 contextOID 會開不起來。"""
    user = service.get_user('S094009', live_db)
    item = service.list_handled(user, live_db, limit=1)['items'][0]
    oid = item['trace_url'].rsplit('=', 1)[1]
    with service.connect(live_db) as database:
        assert database.scalar('SELECT COUNT(*) FROM ProcessInstance WHERE OID = ?', (oid,)) == 1
        assert database.scalar(
            'SELECT COUNT(*) FROM ProcessInstance WHERE contextOID = ?', (oid,)) == 0


def test_instance_detail_has_fields_and_history(live_db):
    detail = service.get_instance('SIC00500000027', live_db)
    assert detail is not None
    assert detail['form_parse_error'] == ''
    values = {f['id']: f['value'] for f in detail['field_values']}
    assert values.get('sqrxm') == '鄭智寬'
    assert detail['approval_history']


def test_instance_fields_carry_chinese_labels(live_db):
    """欄位要帶表單定義裡的中文名，並依版面順序排列。"""
    detail = service.get_instance('SIC00500000027', live_db)
    assert detail['form_id'] == 'MIS_Application'
    assert detail['form_name'] == 'MIS問題反應單'
    assert detail['label_source_error'] == ''
    names = {f['id']: f['name'] for f in detail['field_values']}
    assert names['ddtype2'] == '項目：'
    assert names['bddh'] == '表單編號：'
    types = {f['id']: f['type'] for f in detail['field_values']}
    assert types['bddh'] == 'SERIAL_NUMBER'


def test_grid_blocks_carry_labels(live_db):
    """Grid 本身有中文名；欄位（列內 item）沒有，維持顯示 ID。"""
    detail = service.get_instance('VISOMod001_v200000007', live_db)
    blocks = {g['id']: g for g in detail['grid_values']}
    assert blocks['Grid_DocServer']['name'] == '設定文件主機'
    assert blocks['Grid_Attachment']['columns']


def test_unknown_field_keeps_value_with_empty_name(live_db):
    """定義裡查不到的欄位不能被丟掉，名稱留空由前端顯示 ID。"""
    fields = service._label_fields({'zzz_not_in_form': 'X'}, {'a': {'name': 'A', 'order': 0}})
    assert fields == [{'id': 'zzz_not_in_form', 'name': '', 'type': '', 'value': 'X'}]


def test_instance_finds_form_when_relevant_data_has_variables_first(live_db):
    """迴歸測試：LocalRelevantData 的第一列是流程變數時也要取到表單。

    這張單的 LocalRelevantData 依 processSerialNumber、ISOMod001 的順序回傳，
    舊版把表單併在同一個 SELECT TOP 1 裡查，會撞到變數列而顯示「表單欄位（0）」。
    """
    detail = service.get_instance('SISOMod00100000933', live_db)
    assert detail is not None
    assert detail['fi_serial_number'] == 'ISOMod00100003347'
    assert len(detail['field_values']) > 0


def test_no_process_instance_loses_form_across_open_cases(live_db):
    """進行中的單裡，能取到表單的比例要與資料庫實際擁有表單的比例相同。"""
    with service.connect(live_db) as database:
        has_form = database.scalar('''
            SELECT COUNT(*) FROM (
                SELECT (SELECT TOP 1 FI.OID FROM LocalRelevantData LRD
                        JOIN FormInstance FI ON FI.OID = LRD.valueOID
                        WHERE LRD.containerOID = PI.contextOID) AS f
                FROM ProcessInstance PI WHERE PI.currentState = 1) t
            WHERE f IS NOT NULL''')
        fetched = database.scalar('''
            SELECT COUNT(*) FROM (
                SELECT (SELECT TOP 1 CAST(FI.fieldValues AS nvarchar(10))
                        FROM LocalRelevantData LRD
                        JOIN FormInstance FI ON FI.OID = LRD.valueOID
                        WHERE LRD.containerOID = PI.contextOID) AS fv
                FROM ProcessInstance PI WHERE PI.currentState = 1) t
            WHERE fv IS NOT NULL''')
    assert fetched == has_form
