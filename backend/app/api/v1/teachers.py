"""教师管理 API 占位。

文档 §3.2 API/v1/teachers.py。
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("", summary="教师列表")
async def list_teachers() -> list[dict[str, str]]:
    """占位：返回教师列表。"""
    return [{"id": "demo-teacher", "name": "示例教师", "role": "teacher"}]