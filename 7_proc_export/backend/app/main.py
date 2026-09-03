# -*- coding: utf-8 -*-
"""FastAPI 入口。

    cd 7_proc_export/backend
    python -m uvicorn app.main:app --reload --port 8002

本服務唯讀：只查詢與匯出，沒有任何寫入端點。
POST 只出現在需要傳結構化查詢條件的地方（查單、匯出），不會改到資料庫。
預設只綁 127.0.0.1，要對外開放必須明確指定 --host。
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import settings
from .routers import catalog, export, instances

app = FastAPI(
    title='BPM 流程與表單匯出',
    description='唯讀查詢鼎新 BPM 的流程單據，並把清單／表單內容／簽核名單'
                '匯出成單一 Excel 的不同 tab。供稽核調閱使用。',
    version='0.1.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.DEV_ORIGINS,
    allow_methods=['GET', 'POST'],
    allow_headers=['*'],
    expose_headers=['Content-Disposition', 'X-Export-Rows', 'X-Export-Signature-Rows'],
)

app.include_router(catalog.router)
app.include_router(instances.router)
app.include_router(export.router)

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
        return FileResponse(os.path.join(settings.FRONTEND_DIST, 'index.html'))
