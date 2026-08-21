"""GPS 意图提取服务（调用 LLM）。

文档 §3.2 services/gps/reasoner.py：
基于 DeepSeek 结构化输出，从用户原始查询中提取结构化教学意图。
"""

import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.gps import ChatMessage
from app.services.llm.provider import chat_llm

logger = logging.getLogger(__name__)

FIXED_SLOTS = ["subject", "grade", "topic", "objectives", "key_points"]


# ── LLM 结构化输出 Schema ─────────────────────────────────────────────────────

class ExtractedIntent(BaseModel):
    """LLM 结构化提取结果（与 TeachingSlots 字段对齐）。"""

    subject: str = Field(default="", max_length=128)
    grade: str = Field(default="", max_length=128)
    topic: str = Field(default="", max_length=255)
    objectives: list[str] = Field(default_factory=list, max_length=10)
    key_points: list[str] = Field(default_factory=list, max_length=10)
    difficulty: str = Field(default="medium", max_length=32)  # easy | medium | hard
    style: str = Field(default="interactive", max_length=64)  # theory | interactive | experiment
    activities: list[str] = Field(default_factory=list, max_length=10)
    prerequisites: list[str] = Field(default_factory=list, max_length=10)

    def to_gps_result(self) -> dict:
        """转为 ClarifyResponse 返回格式。"""
        return {
            "subject": self.subject,
            "grade": self.grade,
            "topic": self.topic,
            "objectives": self.objectives,
            "key_points": self.key_points,
            "difficulty": self.difficulty,
            "style": self.style,
            "confidence": self._compute_confidence(),
        }

    @property
    def result(self) -> "ExtractedIntent":
        """兼容旧版测试/调用方式。"""
        return self

    @property
    def missing_slots(self) -> list[dict[str, str]]:
        missing = []
        for slot in FIXED_SLOTS:
            value = getattr(self, slot, None)
            if not value:
                missing.append({"slot": slot, "reason": f"缺少{slot}信息"})
        return missing

    @property
    def needs_more_info(self) -> bool:
        return bool(self.missing_slots)

    @property
    def suggestion(self) -> Optional[str]:
        if not self.missing_slots:
            return None
        return self.missing_slots[0]["reason"]

    def _compute_confidence(self) -> float:
        """根据已填槽位数估算置信度。"""
        filled = sum(
            1
            for v in [
                self.subject,
                self.grade,
                self.topic,
                self.objectives,
                self.key_points,
            ]
            if v
        )
        return round(filled / 5, 2)


# ── Prompt 模板 ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """你是一位资深教育专家，擅长从教师的简短描述中精准提取结构化教学意图。

请根据用户的输入，提取以下字段（json_object 格式）：

| 字段 | 说明 | 示例 |
|------|------|------|
| subject | 科目 | 物理、化学、数学 |
| grade | 年级 | 初中一年级、高中二年级 |
| topic | 课题/主题 | 浮力、光合作用 |
| objectives | 学习目标（最多3条） | ["理解阿基米德原理"] |
| key_points | 教学重点（最多3条） | ["浮力公式 F=ρgV"] |
| difficulty | 难度：easy / medium / hard | medium |
| style | 授课风格：theory / interactive / experiment | interactive |
| activities | 课堂活动建议（最多2条） | ["分组实验"] |
| prerequisites | 先备知识（最多2条） | ["力的合成"] |

规则：
- 只填写你从输入中能**明确推断**的内容，不要编造
- 无法推断的字段留空字符串或空列表
- difficulty 和 style 基于内容和学生年级综合判断
- objectives 和 key_points 必须是教师在输入中直接或隐含表达的内容"""

_USER_PROMPT_TEMPLATE = """教师输入：
{query}

{context_block}
"""


def _build_context_block(materials_context: Optional[str] = None) -> str:
    if not materials_context:
        return ""
    return f"\n参考材料摘要：\n{materials_context}\n"


# ── 核心提取函数 ───────────────────────────────────────────────────────────────

async def extract_intent(
    query: str | list[ChatMessage],
    materials_context: Optional[str] = None,
) -> ExtractedIntent:
    """从用户查询中提取结构化教学意图。

    Args:
        query: 教师原始输入
        materials_context: 参考材料摘要（可选）

    Returns:
        ExtractedIntent 实例，字段对齐 TeachingSlots
    """
    if isinstance(query, list):
        query_text = "\n".join(f"{msg.role}: {msg.content}" for msg in query)
    else:
        query_text = query

    context_block = _build_context_block(materials_context)
    user_content = _USER_PROMPT_TEMPLATE.format(
        query=query_text,
        context_block=context_block,
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        text = await chat_llm(messages, temperature=0.2, max_tokens=1024)
        parsed = json.loads(text)
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
        result = ExtractedIntent.model_validate(parsed)
        logger.info(
            "[GPS Reasoner] 提取成功 topic=%s grade=%s subject=%s",
            result.topic,
            result.grade,
            result.subject,
        )
        return result
    except Exception as exc:
        logger.error("[GPS Reasoner] 提取异常：%s", exc)
        return ExtractedIntent()
