# -*- coding: utf-8 -*-
"""FastAPI 服務進入點。

啟動方式：
    cd 5_ws_explorer/backend
    python -m uvicorn app.main:app --reload --port 8001
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import settings
from .routers import api_meta, form_edit, invoke

app = FastAPI(
    title='鼎新 BPM WorkflowService API 檢視與實測工具',
    description='展示 NaNaWeb WorkflowService API 介面規格、實測樣本與線上即時測試。',
    version='0.1.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.DEV_ORIGINS,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['*'],
)

app.include_router(api_meta.router)
app.include_router(invoke.router)
app.include_router(form_edit.router)

# 前端建置產物存在時掛載，讓單一服務即可直接運行完整前端
if os.path.isdir(settings.FRONTEND_DIST):
    app.mount('/assets',
              StaticFiles(directory=os.path.join(settings.FRONTEND_DIST, 'assets')),
              name='assets')

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(os.path.join(settings.FRONTEND_DIST, 'index.html'))

    @app.get('/{path:path}', include_in_schema=False)
    def spa_fallback(path: str):
        """Vue Router / SPA fallback。"""
        return FileResponse(os.path.join(settings.FRONTEND_DIST, 'index.html'))
