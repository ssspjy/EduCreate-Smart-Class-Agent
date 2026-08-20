"""PPT 质检 API。

文档 §3.2 API/v1/quality.py：
- POST /quality/check — 基于大纲结构进行可解释规则评估（清晰度 / 覆盖度 / 互动性）
"""

import logging
from pydantic import BaseModel

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 请求 / 响应 ────────────────────────────────────────────────────────────────

class QualityCheckRequest(BaseModel):
    title: str
    subject: str = ""
    grade: str = ""
    sections: list[dict]
    total_slides: int = 0
    total_duration_minutes: int = 0


class QualityReportResponse(BaseModel):
    score: float      # 综合评分 0~100
    clarity: float    # 清晰度 0~1
    coverage: float   # 覆盖度 0~1
    engagement: float # 互动性 0~1
    suggestions: list[str]


# ── 规则评估函数 ──────────────────────────────────────────────────────────────

def _score_clarity(outline: QualityCheckRequest) -> tuple[float, list[str]]:
    """清晰度：评估标题表达、章节结构、逻辑连贯性。"""
    score = 0.0
    suggestions = []

    # 标题有课题关键字 +3
    if outline.title and any(kw in outline.title for kw in ["：", "—", "-", "《"]):
        score += 0.3

    # 每个章节有明确标题 +2
    titled_sections = [s for s in outline.sections if s.get("title")]
    if titled_sections:
        score += min(0.3, len(titled_sections) * 0.05)

    # 每个章节有 bullet 点 +2
    sections_with_bullets = [s for s in outline.sections if s.get("bullets")]
    if sections_with_bullets:
        score += min(0.2, len(sections_with_bullets) * 0.04)

    # 总分合理（10~60 页） +2
    ts = outline.total_slides or 0
    if 10 <= ts <= 60:
        score += 0.2
    elif ts < 5:
        suggestions.append("总页数偏少，建议补充更多内容或细分知识点")
    elif ts > 80:
        suggestions.append("总页数偏多，建议精简章节内容")

    # 归一化到 0~1
    clarity = min(1.0, score)
    return clarity, suggestions


def _score_coverage(outline: QualityCheckRequest) -> tuple[float, list[str]]:
    """覆盖度：评估知识点覆盖、难度适配、目标完整性。"""
    score = 0.0
    suggestions = []

    # 章节数量 3~8 个为佳
    n = len(outline.sections)
    if 3 <= n <= 8:
        score += 0.4
    elif n < 3:
        suggestions.append("章节数量偏少，建议拆分更多小节")
        score += 0.2
    else:
        suggestions.append("章节数量偏多，建议合并部分章节")

    # 每个章节有 duration_minutes 估算
    with_duration = [s for s in outline.sections if s.get("duration_minutes")]
    if with_duration:
        score += min(0.3, len(with_duration) * 0.05)

    # 涵盖引入/练习/小结全流程
    titles = " ".join(s.get("title", "") for s in outline.sections)
    has_intro = any(kw in titles for kw in ["引入", "导入"])
    has_practice = any(kw in titles for kw in ["练习", "实践", "活动"])
    has_summary = any(kw in titles for kw in ["小结", "总结", "作业"])

    if has_intro and has_practice and has_summary:
        score += 0.3
    else:
        missing_parts = []
        if not has_intro: missing_parts.append("引入")
        if not has_practice: missing_parts.append("练习")
        if not has_summary: missing_parts.append("小结/作业")
        suggestions.append(f"建议补充完整教学环节：{'、'.join(missing_parts)}")

    coverage = min(1.0, score)
    return coverage, suggestions


def _score_engagement(outline: QualityCheckRequest) -> tuple[float, list[str]]:
    """互动性：评估互动设计、提问安排、活动设计。"""
    score = 0.0
    suggestions = []

    # 检查 keywords
    engagement_keywords = [
        "讨论", "分组", "互动", "提问", "思考",
        "探究", "实验", "演示", "同桌", "小组",
    ]
    all_bullets = " ".join(
        b for s in outline.sections for b in s.get("bullets", [])
    )
    matched_kws = [kw for kw in engagement_keywords if kw in all_bullets]

    score += min(0.6, len(matched_kws) * 0.08)

    # 包含练习/活动章节
    has_activity = any(kw in " ".join(s.get("title", "") for s in outline.sections)
                     for kw in ["练习", "活动", "实践", "探究"])
    if has_activity:
        score += 0.3
    else:
        suggestions.append("建议增加课堂互动环节，如分组讨论或探究活动")

    # 时长分配合理性（加分项都用完后，若总得分仍偏低则建议）
    if not has_activity and len(matched_kws) == 0:
        suggestions.append("建议减少纯讲授比例，增加师生互动环节")

    engagement = min(1.0, score)
    return engagement, suggestions


# ── 核心接口 ──────────────────────────────────────────────────────────────────

@router.post("/check", response_model=QualityReportResponse, summary="质检 PPT 大纲")
async def quality_check(body: QualityCheckRequest) -> QualityReportResponse:
    """基于大纲结构进行可解释规则评估。

    评分维度：
    - clarity（清晰度）：标题、章节结构、逻辑连贯
    - coverage（覆盖度）：知识点覆盖、难度适配、目标完整
    - engagement（互动性）：互动设计、提问安排、活动设计

    总分 = clarity*0.35 + coverage*0.35 + engagement*0.30
    """
    clarity, cl_sug = _score_clarity(body)
    coverage, cov_sug = _score_coverage(body)
    engagement, eng_sug = _score_engagement(body)

    # 综合评分（百分制）
    raw_score = clarity * 0.35 + coverage * 0.35 + engagement * 0.30
    score = round(raw_score * 100, 1)

    # 合并去重建议
    all_suggestions = list(dict.fromkeys([*cl_sug, *cov_sug, *eng_sug]))[:5]

    logger.info(
        "[Quality] score=%.1f clarity=%.2f coverage=%.2f engagement=%.2f",
        score, clarity, coverage, engagement,
    )

    return QualityReportResponse(
        score=score,
        clarity=round(clarity, 2),
        coverage=round(coverage, 2),
        engagement=round(engagement, 2),
        suggestions=all_suggestions,
    )
