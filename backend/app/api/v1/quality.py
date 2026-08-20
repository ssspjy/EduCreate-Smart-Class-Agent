"""质量检测 API。

前端 §4.5 质检页面：清晰度 / 覆盖度 / 互动性评分 + 优化建议。
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class OutlineSection(BaseModel):
    id: str
    title: str
    bullets: list[str]
    duration_minutes: int
    slide_count: int


class OutlineBody(BaseModel):
    title: str
    subject: str
    grade: str
    sections: list[OutlineSection]
    total_slides: int
    total_duration_minutes: int


class QualityReport(BaseModel):
    score: int          # 0-100
    clarity: float       # 0-10
    coverage: float      # 0-10
    engagement: float    # 0-10
    suggestions: list[str]


@router.post("/check", response_model=QualityReport, summary="PPT 大纲质量检测")
async def quality_check(outline: OutlineBody) -> QualityReport:
    """占位：调用 PPTAgent PPTEval 对大纲进行质量评估。

    实际接入时：outline -> PPTEval -> QualityReport。
    """
    section_count = len(outline.sections)
    total_slides = outline.total_slides
    duration = outline.total_duration_minutes

    # 模拟评分逻辑（接入真实模型后替换）
    clarity = 7.5 if section_count >= 4 else 6.0
    coverage = 8.0 if total_slides >= 10 else 6.5
    engagement = 7.0 if section_count <= 7 else 6.0
    score = int((clarity + coverage + engagement) / 3 * 10)

    suggestions = []
    if section_count < 3:
        suggestions.append("章节数量偏少，建议至少设置 3 个主要章节。")
    if total_slides < 5:
        suggestions.append("总页数较少，可适当扩展重点章节的详细内容。")
    if duration > 45:
        suggestions.append("课时较长，建议控制在 40 分钟以内，避免学生疲劳。")
    if not suggestions:
        suggestions.append("大纲结构清晰，内容覆盖合理，可以进入下一步导出。")

    return QualityReport(
        score=score,
        clarity=clarity,
        coverage=coverage,
        engagement=engagement,
        suggestions=suggestions,
    )
