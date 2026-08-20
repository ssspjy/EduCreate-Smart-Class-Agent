"""FastAPI 应用入口。

最小可运行骨架：
- /health：存活探针
- /api/v1：v1 路由前缀
- CORS：允许本地前端开发端口 5173 跨域
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize local skeleton storage during app startup."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="师创智课 - 教育内容智能创作与课堂代理",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """存活探针。"""
    return {"status": "ok", "version": settings.app_version}


app.include_router(api_router, prefix=settings.api_v1_prefix)
