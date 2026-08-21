# -*- coding: utf-8 -*-
"""權限寫入端點。

**只在 BPM_VIEWER_ENABLE_WRITE=1 時才被註冊** —— 沒開旗標連路由都不存在，
不是靠執行期檢查擋。流程還必須列在 BPM_VIEWER_WRITABLE_PROCESSES 白名單中。
"""

from fastapi import APIRouter, HTTPException, Request

from .. import writer
from ..models import (BackupEntry, PermissionApplyResult, PermissionPreview,
                      PermissionRequest, RestoreResult)

router = APIRouter(prefix='/api', tags=['write'])


def _guard(func, *args):
    """把 WriteError 轉成 400，訊息原樣回給使用者。"""
    try:
        return func(*args)
    except writer.WriteError as exc:
        raise HTTPException(400, str(exc))


@router.post('/processes/{process_id}/activities/{activity_id}/permissions/preview',
             response_model=PermissionPreview)
def preview_permissions(process_id: str, activity_id: str,
                        body: PermissionRequest, host: str = ''):
    """回傳 舊值 → 新值 的差異與套用 token，不寫入任何東西。"""
    items = [item.model_dump() for item in body.items]
    return _guard(writer.preview, process_id, activity_id, items, host)


@router.patch('/processes/{process_id}/activities/{activity_id}/permissions',
              response_model=PermissionApplyResult)
def apply_permissions(process_id: str, activity_id: str, body: PermissionRequest,
                      request: Request, host: str = ''):
    """實際套用。token 必填且必須來自 preview。"""
    if not body.token:
        raise HTTPException(400, '缺少 token，請先呼叫 preview')
    items = [item.model_dump() for item in body.items]
    actor = request.client.host if request.client else ''
    return _guard(writer.apply, process_id, activity_id, items, body.token, actor, host)


@router.get('/write/backups', response_model=list[BackupEntry])
def list_backups():
    return writer.list_backups()


@router.post('/write/restore/{backup_id}', response_model=RestoreResult)
def restore_backup(backup_id: str, host: str = ''):
    return _guard(writer.restore, backup_id, host)
