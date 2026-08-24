# -*- coding: utf-8 -*-
"""SOAP 即時實測端點。"""

from fastapi import APIRouter

from ..schemas import InvokeRequest, InvokeResult
from ..service import service

router = APIRouter(prefix='/api', tags=['invoke'])


@router.post('/invoke', response_model=InvokeResult)
def invoke_operation(req: InvokeRequest):
    """即時呼叫 191 測試區的 WorkflowService SOAP API。

    - 嚴格禁止連線 190 正式區。
    - 具有副作用的方法（write）必須帶有 allowWrite=True 才能執行。
    """
    return service.invoke(
        operation_name=req.operationName,
        input_message=req.inputMessage,
        params=req.params,
        allow_write=req.allowWrite,
        endpoint=req.endpoint,
    )
