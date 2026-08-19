"""v1 版本路由汇总（按 §3.2 文档注册全部模块）。"""

from fastapi import APIRouter

from app.api.v1 import auth, exports, knowledge, lessons, materials, teachers

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(teachers.router, prefix="/teachers", tags=["teachers"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])