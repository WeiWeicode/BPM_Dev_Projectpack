# -*- coding: utf-8 -*-
"""關卡工作台端點：看歷程 → 以該關卡的人操作 → 簽收／簽核／轉派／取回／收單。

除了 GET /board 之外全都是寫入，一律要求 confirm=true。
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from .. import workitem
from ..schemas import (
    AcceptRequest,
    AcceptResult,
    ActivityBoard,
    CloseProcessRequest,
    CloseProcessResult,
    CompleteRequest,
    CompleteResult,
    ReassignRequest,
    ReassignResult,
    ReexecuteRequest,
    ReexecuteResult,
)

router = APIRouter(prefix='/api/workitem', tags=['workitem'])


def _guard(func, *args, **kwargs):
    """預期內錯誤轉 400，其餘往上拋（不吞例外）。"""
    try:
        return func(*args, **kwargs)
    except workitem.WorkItemError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get('/board/{serialNo}', response_model=ActivityBoard)
def board(serialNo: str, endpoint: Optional[str] = Query(None)):
    """關卡歷程 + 目前關卡的待辦人與工作項目 OID（含 Users.OID）。"""
    return _guard(workitem.load_activities, serialNo, endpoint)


@router.post('/accept', response_model=AcceptResult)
def accept(req: AcceptRequest):
    """以該關卡的人簽收待辦。"""
    return _guard(workitem.accept, req.workItemOID, req.userId,
                  req.confirm, req.endpoint)


@router.post('/complete', response_model=CompleteResult)
def complete(req: CompleteRequest):
    """（可先改表單）再簽核推進到下一關。"""
    return _guard(workitem.complete, req.serialNo, req.workItemOID, req.userId,
                  req.comment, req.changes, req.autoAccept, req.confirm,
                  req.endpoint)


@router.post('/reassign', response_model=ReassignResult)
def reassign(req: ReassignRequest):
    """轉派待辦（管理者強制／自行轉派／變更擁有者）。"""
    return _guard(workitem.reassign, req.workItemOID, req.acceptorId,
                  req.comment, req.mode, req.requesterId, req.confirm,
                  req.endpoint)


@router.post('/reexecute', response_model=ReexecuteResult)
def reexecute(req: ReexecuteRequest):
    """取回重辦：把已簽核的關卡叫回來。"""
    return _guard(workitem.reexecute, req.serialNo, req.askUserId,
                  req.activityId, req.comment, req.confirm, req.endpoint)


@router.post('/close', response_model=CloseProcessResult)
def close_process(req: CloseProcessRequest):
    """收單：作廢或終止整張單。"""
    return _guard(workitem.close_process, req.serialNo, req.mode, req.userId,
                  req.comment, req.confirm, req.endpoint)
