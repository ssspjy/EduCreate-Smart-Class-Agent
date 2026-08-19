"""教案 / 课件生成 API。

文档 §3.2 API/v1/lessons.py：教案 / 课件生成。
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class LessonRequest(BaseModel):
    """课件生成请求。"""

    subject: str
    topic: str
    grade: str


class LessonResponse(BaseModel):
    """课件生成响应。"""

    lesson_id: str
    status: str


@router.post("/generate", summary="生成教案 + 课件")
async def generate_lesson(req: LessonRequest) -> LessonResponse:
    """占位：触发 GPS + PPTAgent 流水线。"""
    return LessonResponse(lesson_id="pending", status="queued")


@router.get("", summary="列出教案")
async def list_lessons() -> list[dict[str, str]]:
    """占位：返回空列表。"""
    return []