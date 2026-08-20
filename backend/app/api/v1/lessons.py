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


# ── GPS 输出结构（前端 UploadPage 传递的 GPS 结果）──────────────
class GpsResult(BaseModel):
    subject: str
    grade: str
    topic: str
    objectives: list[str]
    key_points: list[str]
    difficulty: str


# ── 大纲章节结构 ────────────────────────────────────────────────
class OutlineSection(BaseModel):
    id: str
    title: str
    bullets: list[str]
    duration_minutes: int
    slide_count: int


class OutlineResponse(BaseModel):
    title: str
    subject: str
    grade: str
    sections: list[OutlineSection]
    total_slides: int
    total_duration_minutes: int


@router.post("/outline", response_model=OutlineResponse, summary="生成 PPT 大纲")
async def generate_outline(gps: GpsResult) -> OutlineResponse:
    """占位：调用 PPTAgent Outliner 基于 GPS 结果生成章节结构。

    实际接入时：gps -> PPTAgent Outliner -> Outline。
    """
    sections = [
        OutlineSection(
            id="1",
            title="引入：生活中的浮力现象",
            bullets=[
                "展示轮船浮在水面",
                "提问：为什么钢铁做的船能浮？",
                "引出浮力概念",
            ],
            duration_minutes=5,
            slide_count=3,
        ),
        OutlineSection(
            id="2",
            title="浮力及其方向",
            bullets=[
                "浮力定义：液体对浸入物体的向上压力差",
                "方向：竖直向上",
                "用弹簧测力计演示",
            ],
            duration_minutes=8,
            slide_count=4,
        ),
        OutlineSection(
            id="3",
            title="阿基米德原理",
            bullets=[
                "实验：测量石块浸没水中时弹簧测力计示数变化",
                "结论：F浮 = G排 = ρ液 g V排",
                "推导过程动画",
            ],
            duration_minutes=15,
            slide_count=7,
        ),
        OutlineSection(
            id="4",
            title="浮力的应用",
            bullets=[
                "轮船：排水量与载重",
                "潜水艇：改变自身重力",
                "热气球：浮力原理",
            ],
            duration_minutes=7,
            slide_count=4,
        ),
        OutlineSection(
            id="5",
            title="课堂小结与练习",
            bullets=[
                "核心公式回顾",
                "3 道典型例题",
                "课后作业布置",
            ],
            duration_minutes=5,
            slide_count=3,
        ),
    ]
    return OutlineResponse(
        title=f"{gps.grade} {gps.subject}：{gps.topic}",
        subject=gps.subject,
        grade=gps.grade,
        sections=sections,
        total_slides=sum(s.slide_count for s in sections),
        total_duration_minutes=sum(s.duration_minutes for s in sections),
    )


@router.post("/generate", summary="生成教案 + 课件")
async def generate_lesson(req: LessonRequest) -> LessonResponse:
    """占位：触发 GPS + PPTAgent 流水线。"""
    return LessonResponse(lesson_id="pending", status="queued")


@router.get("", summary="列出教案")
async def list_lessons() -> list[dict[str, str]]:
    """占位：返回空列表。"""
    return []
