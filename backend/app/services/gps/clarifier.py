"""GPS 澄清会话状态管理。

文档 §3.2 services/gps/clarifier.py。

职责：
1. 管理多轮对话状态（在内存中追踪当前会话的 slots 填充进度）
2. 提供缺失槽位检测（固定槽位 + 动态追问）
3. 为 API 层提供统一的澄清入口
"""

from typing import Optional

from app.schemas.gps import GpsClarifyResult, MissingSlot


# ── 固定槽位定义 ─────────────────────────────────────────────────────────────

FIXED_SLOTS = [
    "subject",
    "grade",
    "topic",
    "objectives",
    "key_points",
    "difficulty",
    "style",
    "duration_min",
]


# ── 槽位描述（用于生成追问） ─────────────────────────────────────────────────

SLOT_HINTS: dict[str, str] = {
    "subject": "科目（如：物理、化学、数学、语文）",
    "grade": "年级（如：初中一年级、高中二年级）",
    "topic": "课题/主题（如：浮力、光合作用）",
    "objectives": "学习目标（如：理解阿基米德原理）",
    "key_points": "教学重点（如：浮力公式 F浮=ρ液gV排）",
    "difficulty": "难度等级（easy / medium / hard）",
    "style": "授课风格（theory / interactive / experiment）",
    "duration_min": "课时时长（分钟数）",
    "activities": "课堂活动安排",
    "prerequisites": "先备知识要求",
}


# ── Clarifier 会话状态 ────────────────────────────────────────────────────────

class ClarifierSession:
    """GPS 澄清会话状态（每次 POST /gps/clarify 新建一个实例）。"""

    def __init__(
        self,
        initial_result: Optional[GpsClarifyResult] = None,
        message_count: int = 0,
    ):
        self.current_result = initial_result
        self.message_count = message_count

    def update(self, result: GpsClarifyResult) -> None:
        """用新一轮提取结果更新会话状态。"""
        self.current_result = result
        self.message_count += 1

    def get_missing_slots(self) -> list[MissingSlot]:
        """返回当前缺失的固定槽位列表。"""
        if self.current_result is None:
            return [
                MissingSlot(slot=slot, reason=f"槽位【{slot}】尚未填写")
                for slot in FIXED_SLOTS
            ]

        result = self.current_result
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

        return missing

    def is_complete(self) -> bool:
        """判断当前槽位是否已填满（不需要追问）。"""
        return len(self.get_missing_slots()) == 0


# ── 全局会话存储（生产环境应换 Redis）─────────────────────────────────────────

# 内存存储：session_id -> ClarifierSession
# key 为前端传入的 session_id 或临时生成的 UUID
_sessions: dict[str, ClarifierSession] = {}


def get_session(session_id: str) -> Optional[ClarifierSession]:
    """获取或创建澄清会话。"""
    if session_id not in _sessions:
        _sessions[session_id] = ClarifierSession()
    return _sessions[session_id]


def create_session(
    session_id: str,
    initial_result: Optional[GpsClarifyResult] = None,
) -> ClarifierSession:
    """创建新澄清会话（覆盖已存在的 session）。"""
    _sessions[session_id] = ClarifierSession(
        initial_result=initial_result,
        message_count=0,
    )
    return _sessions[session_id]


def clear_session(session_id: str) -> None:
    """清除会话（对话结束后调用）。"""
    _sessions.pop(session_id, None)


# ── 公开接口 ───────────────────────────────────────────────────────────────────

async def missing_slots(result: Optional[GpsClarifyResult] = None) -> list[str]:
    """返回缺失的固定槽位名称列表（兼容原占位接口）。"""
    session = ClarifierSession(initial_result=result)
    return [ms.slot for ms in session.get_missing_slots()]
