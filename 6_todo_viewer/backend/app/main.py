# -*- coding: utf-8 -*-
"""FastAPI 入口。

    uvicorn app.main:app --reload --port 8100

本服務唯讀：**只註冊 GET 端點，不存在任何寫入路徑**，也不呼叫任何 SOAP API。
預設只綁 127.0.0.1，要對外開放必須明確指定 --host。
"""

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import models, service, settings

app = FastAPI(
    title='BPM 待辦與流程查詢器',
    description='唯讀查詢鼎新 BPM 的流程實例：待簽核、我申請的、我經辦過的。',
    version='0.1.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.DEV_ORIGINS,
    allow_methods=['GET'],
    allow_headers=['*'],
)

HostParam = Query(default=None, description='資料來源主機，見 /api/hosts')


@app.get('/api/health', response_model=models.Health, tags=['meta'])
def read_health(host: str = HostParam):
    return service.health(host)


@app.get('/api/hosts', response_model=list[models.HostOption], tags=['meta'])
def read_hosts():
    return service.host_list()


@app.get('/api/users/search', response_model=list[models.UserCandidate], tags=['users'])
def search_users(q: str = Query(min_length=1, description='員工編號、姓名或信箱'),
                 host: str = HostParam):
    """一律回候選清單 —— 同一個人可能有多個公司別帳號，由使用者自己挑。"""
    return service.search_users(q, host)


def _require_user(user_id, host):
    user = service.get_user(user_id, host)
    if user is None:
        raise HTTPException(status_code=404, detail='查無使用者：%s' % user_id)
    return user


@app.get('/api/users/{user_id}/todo', response_model=models.TodoList, tags=['tasks'])
def read_todo(user_id: str, host: str = HostParam):
    return service.list_todo(_require_user(user_id, host), host)


@app.get('/api/users/{user_id}/requested', response_model=models.RequestedList,
         tags=['tasks'])
def read_requested(user_id: str,
                   state: int = Query(default=None, description='流程狀態，省略為全部'),
                   offset: int = Query(default=0, ge=0),
                   limit: int = Query(default=settings.DEFAULT_LIMIT, ge=1,
                                      le=settings.MAX_LIMIT),
                   host: str = HostParam):
    return service.list_requested(_require_user(user_id, host), host, state, offset, limit)


@app.get('/api/users/{user_id}/handled', response_model=models.HandledList, tags=['tasks'])
def read_handled(user_id: str,
                 offset: int = Query(default=0, ge=0),
                 limit: int = Query(default=settings.DEFAULT_LIMIT, ge=1,
                                    le=settings.MAX_LIMIT),
                 host: str = HostParam):
    return service.list_handled(_require_user(user_id, host), host, offset, limit)


@app.get('/api/instances/{serial_number}', response_model=models.InstanceDetail,
         tags=['instances'])
def read_instance(serial_number: str,
                  user_id: str = Query(default='', description='檢視者，只用來組追蹤網址'),
                  host: str = HostParam):
    detail = service.get_instance(serial_number, host, user_id)
    if detail is None:
        raise HTTPException(status_code=404, detail='查無此單號：%s' % serial_number)
    return detail


# 前端建置產物存在時掛載，讓正式環境只需跑這一個 process
if os.path.isdir(settings.FRONTEND_DIST):
    app.mount('/assets',
              StaticFiles(directory=os.path.join(settings.FRONTEND_DIST, 'assets')),
              name='assets')

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(os.path.join(settings.FRONTEND_DIST, 'index.html'))
