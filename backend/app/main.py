# SolArc-Ultimate — 极限飞盘队伍管理&战力评分系统
# Copyright 2026 SolArc-Ultimate contributors. MIT License.
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.limiter import limiter
from app.core.middleware import RequestLoggingMiddleware
from app.core.paths import get_docs_dir, get_uploads_dir
from app.services.live_draft_cleanup_service import run_live_draft_cleanup_loop, stop_cleanup_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 安全检查：生产环境不允许使用默认密钥
    if not settings.DEBUG and settings.SECRET_KEY == "change-me-in-production-use-openssl-rand-hex-32":
        raise RuntimeError(
            "SECRET_KEY 使用了默认值，在生产环境中禁止启动。"
            "请在 .env 中设置安全的 SECRET_KEY。"
        )
    await init_db()
    cleanup_stop_event = asyncio.Event()
    cleanup_task = asyncio.create_task(run_live_draft_cleanup_loop(cleanup_stop_event))
    try:
        yield
    finally:
        await stop_cleanup_task(cleanup_task, cleanup_stop_event)


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description=settings.APP_NAME_CN,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
# SlowAPI 应用层限流
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(api_router, prefix="/api/v1")

# 挂载上传文件目录（头像/队徽）
app.mount("/uploads", StaticFiles(directory=get_uploads_dir()), name="uploads")
docs_dir = get_docs_dir()
os.makedirs(docs_dir, exist_ok=True)  # 确保目录存在（首次启动时为空也能正常挂载）
app.mount("/docs-files", StaticFiles(directory=docs_dir), name="docs-files")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
