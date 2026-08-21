# -*- coding: utf-8 -*-
"""FastAPI 入口。

    uvicorn app.main:app --reload --port 8000

本服務唯讀：只註冊 GET 端點，不提供任何寫入路徑。
預設只綁 127.0.0.1，要對外開放必須明確指定 --host。
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import settings
from .routers import forms, meta, processes

app = FastAPI(
    title='BPM 線上結構檢視器',
    description='唯讀呈現鼎新 BPM 資料庫中已發佈（RELEASED）的表單與流程結構。',
    version='0.1.0',
)

# 只在開發時需要：正式部署由本服務直接吐靜態檔，同源無需 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.DEV_ORIGINS,
    allow_methods=['GET', 'POST', 'PATCH'] if settings.ENABLE_WRITE else ['GET'],
    allow_headers=['*'],
    expose_headers=['X-Total-Count'],
)

app.include_router(meta.router)
app.include_router(forms.router)
app.include_router(processes.router)

# 寫入路由只在旗標開啟時註冊 —— 沒開時這些路徑根本不存在
if settings.ENABLE_WRITE:
    from .routers import write
    app.include_router(write.router)

# 前端建置產物存在時掛載，讓正式環境只需跑這一個 process
if os.path.isdir(settings.FRONTEND_DIST):
    app.mount('/assets',
              StaticFiles(directory=os.path.join(settings.FRONTEND_DIST, 'assets')),
              name='assets')

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(os.path.join(settings.FRONTEND_DIST, 'index.html'))

    @app.get('/{path:path}', include_in_schema=False)
    def spa_fallback(path):
        """Vue Router 的 history 模式：非 API 路徑一律交給前端處理。"""
        return FileResponse(os.path.join(settings.FRONTEND_DIST, 'index.html'))
