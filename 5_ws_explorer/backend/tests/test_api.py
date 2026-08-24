# -*- coding: utf-8 -*-
"""5_ws_explorer 後端 API 測試。"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402
from app.service import classify_level, extract_shape  # noqa: E402

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
    assert data['verifiedCount'] >= 29
    assert data['documentedCount'] >= 39
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
