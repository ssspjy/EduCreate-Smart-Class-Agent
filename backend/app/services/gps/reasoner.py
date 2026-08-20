"""GPS 教学意图结构化提取。

文档 §3.2 services/gps/reasoner.py。

实现逻辑：
1. 接收多轮对话历史 + 参考资料的 chunks 作为上下文
2. 构建 LLM prompt，引导结构化提取 TeachingSlots 字段
3. 解析 LLM 输出为 GpsClarifyResult
4. 计算缺失槽位和置信度
"""

import json
import re
from typing import Optional

from app.schemas.gps import (
    ChatMessage,
    ClarifyResponse,
    DifficultyLevel,
    GpsClarifyResult,
    MissingSlot,
)
from app.schemas.lesson_ir import DialogueTurn, TeachingSlots
from app.services.llm import chat_llm

# ── Prompt 模板 ────────────────────────────────────────────────────────────────

_SLOT_DESCRIPTIONS = {
    "subject": "科目，如：物理、化学、数学、语文",
    "grade": "年级，如：初中一年级、高中二年级",
    "topic": "课题/主题，如：浮力、光合作用",
    "duration_min": "课时时长（分钟数）",
    "difficulty": "难度：easy | medium | hard",
    "style": "授课风格：theory | interactive | experiment",
    "objectives": "学习目标列表，如：理解阿基米德原理",
    "key_points": "教学重点列表，如：浮力公式 F浮=ρ液gV排",
    "activities": "课堂活动安排，如：分组实验、小组讨论",
    "prerequisites": "先备知识要求，如：力的合成与分解",
}

_SYSTEM_PROMPT = f"""你是一个专业的教育意图分析助手，负责从教师的描述中提取结构化的教学意图。

请严格按以下 JSON 格式输出，不要输出其他内容：

{{
  "subject": "科目",
  "grade": "年级",
  "topic": "课题",
  "duration_min": 45,
  "difficulty": "easy | medium | hard",
  "style": "theory | interactive | experiment",
  "objectives": ["目标1", "目标2"],
  "key_points": ["重点1", "重点2"],
  "activities": ["活动1"],
  "prerequisites": ["先备知识"]
}}

字段说明：
- subject: 必填，未提及则返回空字符串 ""
- grade: 必填，未提及则返回空字符串 ""
- topic: 必填，未提及则返回空字符串 ""
- difficulty: 根据描述推断，默认 medium
- style: 未明确说明则默认 interactive
- objectives/key_points/activities/prerequisites: 至少返回一个元素数组，无则返回 []
- 如果某个字段无法确定，返回空字符串或空数组
"""


def _build_context(messages: list[ChatMessage], materials_context: str) -> str:
    """构建 LLM 上下文文本。"""
    parts = []
    if materials_context:
        parts.append(f"【参考资料摘要】\n{materials_context}\n")
    if messages:
        parts.append("【对话历史】")
        for msg in messages:
            role = "教师" if msg.role == "user" else "助手"
            parts.append(f"- {role}：{msg.content}")
    return "\n".join(parts)


def _parse_llm_json(raw: str) -> dict:
    """从 LLM 返回中提取 JSON。"""
    raw = raw.strip()
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _normalize_result(data: dict, prev_result: Optional[GpsClarifyResult] = None) -> GpsClarifyResult:
    """将 LLM 解析结果规范化为 GpsClarifyResult。"""
    prev = prev_result

    def _str(val) -> str:
        return str(val).strip() if val else ""

    def _list(val) -> list[str]:
        if isinstance(val, list):
            return [str(v).strip() for v in val if v]
        if val:
            return [str(val).strip()]
        return []

    difficulty_raw = _str(data.get("difficulty", "medium")).lower()
    if difficulty_raw not in ("easy", "medium", "hard"):
        difficulty_raw = "medium"

    style_raw = _str(data.get("style", "interactive")).lower()
    if style_raw not in ("theory", "interactive", "experiment"):
        style_raw = "interactive"

    return GpsClarifyResult(
        subject=_str(data.get("subject")) or (prev.subject if prev else ""),
        grade=_str(data.get("grade")) or (prev.grade if prev else ""),
        topic=_str(data.get("topic")) or (prev.topic if prev else ""),
        objectives=_list(data.get("objectives")) or (prev.objectives if prev else []),
        key_points=_list(data.get("key_points")) or (prev.key_points if prev else []),
        difficulty=DifficultyLevel(difficulty_raw),
        style=style_raw,
        confidence=_compute_confidence(data, prev),
    )


def _compute_confidence(data: dict, prev: Optional[GpsClarifyResult] = None) -> float:
    """计算 GPS 置信度（0~1）。"""
    required_fields = ["subject", "grade", "topic"]
    filled = sum(1 for f in required_fields if data.get(f))
    base = filled / len(required_fields)

    extras = ["objectives", "key_points"]
    for f in extras:
        val = data.get(f)
        if val and (isinstance(val, list) and len(val) > 0):
            base += 0.1

    base = min(base, 1.0)
    if prev:
        base = (base + prev.confidence) / 2
    return round(base, 2)


# ── 公开接口 ───────────────────────────────────────────────────────────────────

async def extract_intent(
    messages: list[ChatMessage],
    materials_context: str = "",
    prev_result: Optional[GpsClarifyResult] = None,
) -> ClarifyResponse:
    """从对话历史和参考资料中提取结构化教学意图。

    Args:
        messages: 多轮对话历史
        materials_context: 参考资料的 chunks 内容摘要（由 API 层传入）
        prev_result: 上一轮提取结果（用于多轮渐进填充）

    Returns:
        ClarifyResponse: 包含提取结果、缺失槽位、是否需要追问
    """
    context = _build_context(messages, materials_context)
    user_msg = messages[-1].content if messages else ""

    system_msg = {"role": "system", "content": _SYSTEM_PROMPT}
    user_llm_msg: dict[str, str] = {
        "role": "user",
        "content": f"{context}\n\n【本轮教师输入】\n{user_msg}" if context else user_msg,
    }

    try:
        raw = await chat_llm([system_msg, user_llm_msg], temperature=0.3, max_tokens=1024)
    except Exception:
        raw = "{}"

    parsed = _parse_llm_json(raw)
    result = _normalize_result(parsed, prev_result)

    missing_slots, needs_more_info = _check_missing_slots(result)

    suggestion = None
    if needs_more_info and missing_slots:
        first_missing = missing_slots[0].slot
        suggestion = _build_suggestion_prompt(first_missing)

    return ClarifyResponse(
        result=result,
        missing_slots=missing_slots,
        needs_more_info=needs_more_info,
        suggestion=suggestion,
    )


def _check_missing_slots(result: GpsClarifyResult) -> tuple[list[MissingSlot], bool]:
    """检测缺失槽位。"""
    missing: list[MissingSlot] = []

    if not result.subject.strip():
        missing.append(MissingSlot(slot="subject", reason="未明确说明科目"))
    if not result.grade.strip():
        missing.append(MissingSlot(slot="grade", reason="未明确说明年级"))
    if not result.topic.strip():
        missing.append(MissingSlot(slot="topic", reason="未明确说明课题"))
    if not result.objectives:
        missing.append(MissingSlot(slot="objectives", reason="未说明学习目标"))
    if not result.key_points:
        missing.append(MissingSlot(slot="key_points", reason="未说明教学重点"))

    needs_more = len(missing) > 0 or result.confidence < 0.7
    return missing, needs_more


def _build_suggestion_prompt(slot: str) -> str:
    """根据缺失槽位生成追问话术。"""
    prompts = {
        "subject": "请告诉我这节课属于哪个科目？（如：物理、化学、数学）",
        "grade": "请问是面向哪个年级的学生？（如：初中一年级、高中二年级）",
        "topic": "请问本次课的主题是什么？（如：浮力、阿基米德原理）",
        "objectives": "您希望通过这节课让学生掌握哪些能力或知识点？",
        "key_points": "这节课的教学重点和难点是什么？",
    }
    return prompts.get(slot, f"关于【{slot}】，能否补充更多信息？")
