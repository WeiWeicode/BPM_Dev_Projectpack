# -*- coding: utf-8 -*-
"""5_ws_explorer 後端 API 測試。"""

import os
import sys
import pytest
from fastapi.testclient import TestClient
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402
from app.service import classify_level, extract_shape  # noqa: E402
# 要排在 app.main 之後：settings 被載入時才會把 5_ws_explorer 根目錄
# 放進 sys.path，form_edit 匯入的 ws_client 就在那裡。
from app import form_edit  # noqa: E402

client = TestClient(app)


def test_classify_level():
    """唯讀與副作用方法分級驗證。"""
    assert classify_level('findFormOIDsOfProcess') == 'read'
    assert classify_level('fetchOrgUnitOfUserId') == 'read'
    assert classify_level('getFormFieldTemplate') == 'read'
    assert classify_level('isUserInRole') == 'read'
    assert classify_level('checkWorkItemState') == 'read'

    # 有副作用之動詞
    assert classify_level('invokeProcess') == 'write'
    assert classify_level('acceptWorkItem') == 'write'
    assert classify_level('abortProcessForSerialNo') == 'write'
    assert classify_level('completeWorkItem') == 'write'
    assert classify_level('reassignWorkItem') == 'write'
    assert classify_level('managementUser') == 'write'  # suspect verb


def test_extract_shape():
    """XML 結構輪廓提取。"""
    xml_sample = '<SimpleProcesses><SimpleProcessInfo><OID>123</OID></SimpleProcessInfo></SimpleProcesses>'
    assert extract_shape(xml_sample) == 'SimpleProcesses > SimpleProcessInfo > OID'
    assert extract_shape('plain_text') == '（非 XML 純值）'
    assert extract_shape(None) is None


def test_api_overview():
    """GET /api/overview 端點測試。"""
    res = client.get('/api/overview')
    assert res.status_code == 200
    data = res.json()
    assert data['operationCount'] == 65
    assert data['verifiedCount'] >= 60
    assert data['documentedCount'] == 65
    assert 'read' in data['levelCounts']
    assert 'write' in data['levelCounts']


def test_api_operations_list_and_filter():
    """GET /api/operations 清單與過濾測試。"""
    res = client.get('/api/operations')
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 65

    # 依 level 篩選
    res_read = client.get('/api/operations?level=read')
    assert res_read.status_code == 200
    for item in res_read.json():
        assert item['level'] == 'read'

    # 依 keyword 搜尋
    res_search = client.get('/api/operations?keyword=findFormOIDsOfProcess')
    assert res_search.status_code == 200
    assert len(res_search.json()) >= 1
    assert res_search.json()[0]['name'] == 'findFormOIDsOfProcess'


def test_api_operation_detail():
    """GET /api/operations/{name} 明細測試。"""
    res = client.get('/api/operations/findFormOIDsOfProcess')
    assert res.status_code == 200
    data = res.json()
    assert data['name'] == 'findFormOIDsOfProcess'
    assert data['level'] == 'read'
    assert len(data['parameters']) == 1
    assert data['parameters'][0]['name'] == 'pProcessPackageId'
    assert data['signature'].startswith('findFormOIDsOfProcess(')


def test_api_seeds():
    """GET /api/seeds 端點測試。"""
    res = client.get('/api/seeds')
    assert res.status_code == 200
    data = res.json()
    assert 'pUserId' in data['seeds']
    assert 'pProcessPackageId' in data['seeds']
    assert len(data['sources']) > 0


def test_invoke_safety_boundary_190():
    """190 正式區連線安全阻擋測試。"""
    res = client.post('/api/invoke', json={
        'operationName': 'findFormOIDsOfProcess',
        'endpoint': 'http://10.10.130.190:9090/NaNaWeb/services/WorkflowService',
        'params': {'pProcessPackageId': 'test'},
    })
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'error'
    assert '190' in data['error']


def test_invoke_safety_boundary_write():
    """副作用方法在 allowWrite=False 時的安全阻擋測試。"""
    res = client.post('/api/invoke', json={
        'operationName': 'invokeProcess',
        'allowWrite': False,
        'params': {},
    })
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'error'
    assert '副作用' in data['error']


# ── 改單工作台 ──────────────────────────────────────────────────
# 這幾項不連 191，只驗證不需要網路的純函式與安全防線。
# 真正的讀寫路徑無法離線測，實測記錄見 form_edit.py 的模組 docstring。

def test_form_edit_parse_and_set():
    """欄位解析與內文替換：屬性不能被動到，值要正確逸出。"""
    xml = ('<TestForm>'
           '<A id="A" dataType="java.lang.String" perDataProId="">舊值</A>'
           '<B id="B" dataType="java.util.Date">2026/08/31</B>'
           '</TestForm>')
    form_id, fields = form_edit.parse_form_xml(xml)
    assert form_id == 'TestForm'
    assert [f['id'] for f in fields] == ['A', 'B']
    assert fields[0]['value'] == '舊值'
    assert fields[0]['attributes']['perDataProId'] == ''

    changed = form_edit.set_field_value(xml, 'A', 'X&Y <Z>')
    assert 'perDataProId=""' in changed          # 屬性原樣保留
    assert 'X&amp;Y &lt;Z&gt;' in changed        # 值有逸出
    assert '<B id="B" dataType="java.util.Date">2026/08/31</B>' in changed


def test_form_edit_rejects_duplicate_tags():
    """重複標籤要拋錯，不能靜默改到第一個。"""
    xml = '<F><A id="A">1</A><A id="A">2</A></F>'
    with pytest.raises(form_edit.FormEditError):
        form_edit.parse_form_xml(xml)


def test_form_edit_unwrap_detects_wrapper():
    """把整包回傳寫回去造成的多層包裝要被偵測並剝開。"""
    inner = '<F><A id="A">值</A></F>'
    healthy = '<com.dsc.nana.services.webservice.FormCollection><forms>' \
              '<com.dsc.nana.services.webservice.FormInfo><fieldValues>%s' \
              '</fieldValues></com.dsc.nana.services.webservice.FormInfo>' \
              '</forms></com.dsc.nana.services.webservice.FormCollection>'
    text, corruption = form_edit.unwrap_field_values(
        healthy % escape(inner))
    assert text == inner
    assert corruption is None

    poisoned = healthy % escape(healthy % escape(inner))
    text, corruption = form_edit.unwrap_field_values(poisoned)
    assert text == inner
    assert corruption and 'FormCollection' in corruption


def test_form_edit_submit_requires_confirm():
    """沒帶 confirm 不得寫入，且必須在連線之前就擋下。"""
    res = client.post('/api/form-edit/submit', json={
        'serialNo': 'X00000001',
        'changes': {'A': 'B'},
    })
    assert res.status_code == 400
    assert '確認' in res.json()['detail']


def test_form_edit_blocks_190():
    """190 正式區在改單頁一樣禁止。"""
    res = client.get('/api/form-edit/instance/X00000001', params={
        'endpoint': 'http://10.10.130.190:9090/NaNaWeb/services/WorkflowService',
    })
    assert res.status_code == 400
    assert '190' in res.json()['detail']
