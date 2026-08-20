"""GPS 教学意图澄清 API。

文档 §3.2 API/v1/gps.py：多轮对话澄清 + 结构化提取。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ClarifyRequest(BaseModel):
    """澄清请求（首次 or 多轮）。"""
    query: Optional[str] = None       # 首次调用
    messages: Optional[list[dict[str, str]]] = None  # 多轮历史
    materials: list[str] = []         # 已上传文件 ID 列表


class GpsResult(BaseModel):
    """GPS 结构化提取结果。"""
    subject: str
    grade: str
    topic: str
    objectives: list[str]
    key_points: list[str]
    difficulty: str   # easy | medium | hard


@router.post("/clarify", response_model=GpsResult, summary="GPS 教学意图澄清")
async def clarify(req: ClarifyRequest) -> GpsResult:
    """占位：调用 GPS Clarifier 从对话中提取教学意图结构。

    实际接入时：messages -> GPS Clarifier -> 结构化结果。
    """
    return GpsResult(
        subject="物理",
        grade="初中三年级",
        topic="浮力",
        objectives=[
            "理解浮力产生的原理",
            "掌握阿基米德原理及其应用",
            "能用浮力知识解释生活中的现象",
        ],
        key_points=[
            "浮力方向：竖直向上",
            "浮力大小：等于排开液体的重力",
            "影响浮力大小的因素：液体密度、排开体积",
        ],
        difficulty="medium",
    )
