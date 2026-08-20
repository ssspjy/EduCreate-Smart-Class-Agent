"""GPS 澄清会话状态管理。

文档 §3.2 services/gps/clarifier.py。

职责：
1. 管理多轮对话状态（在内存中追踪当前会话的 slots 填充进度）
2. 提供缺失槽位检测（固定槽位 + 动态追问）
3. 为 API 层提供统一的澄清入口
"""

import threading
import time
from dataclasses import dataclass, field
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

@dataclass
class DialogueEntry:
    """单条对话记录（用于 DAG 可视化）。"""

    role: str          # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    new_filled_slots: list[str] = field(default_factory=list)  # 本轮新填充的槽位


class ClarifierSession:
    """GPS 澄清会话状态（每个 session_id 对应一个实例）。

    线程安全：使用 threading.Lock 保护状态修改。
    """

    MAX_DIALOGUE_ENTRIES = 50   # 最多保留 50 轮对话，防止内存泄漏
    MAX_MESSAGE_COUNT = 20      # 最多追问 20 轮，防止无限追问

    def __init__(
        self,
        session_id: str,
        initial_result: Optional[GpsClarifyResult] = None,
    ):
        self.session_id = session_id
        self.current_result = initial_result
        self.message_count = 0
        self.created_at = time.time()
        self.last_updated = time.time()
        self.dialogue_entries: list[DialogueEntry] = []
        self._lock = threading.Lock()

    # ── 对话历史追踪 ──────────────────────────────────────────────────────────

    def add_user_message(self, content: str) -> None:
        """记录教师消息。"""
        with self._lock:
            self.dialogue_entries.append(DialogueEntry(role="user", content=content))
            self._trim_entries()

    def add_assistant_message(
        self,
        content: str,
        new_filled_slots: Optional[list[str]] = None,
    ) -> None:
        """记录助手回复及本轮新填充的槽位。"""
        with self._lock:
            entry = DialogueEntry(
                role="assistant",
                content=content,
                new_filled_slots=new_filled_slots or [],
            )
            self.dialogue_entries.append(entry)
            self._trim_entries()

    def _trim_entries(self) -> None:
        """超过上限时裁剪最早的对话记录（保留开头和结尾各一条）。"""
        if len(self.dialogue_entries) > self.MAX_DIALOGUE_ENTRIES:
            # 保留最近 MAX_DIALOGUE_ENTRIES 条
            self.dialogue_entries = self.dialogue_entries[-self.MAX_DIALOGUE_ENTRIES:]

    def get_dialogue_entries(self) -> list[DialogueEntry]:
        """返回当前对话记录列表（线程安全复制）。"""
        with self._lock:
            return list(self.dialogue_entries)

    # ── 槽位更新 ──────────────────────────────────────────────────────────────

    def update(self, result: GpsClarifyResult) -> list[str]:
        """用新一轮提取结果更新会话状态。

        Returns:
            新填充的槽位名称列表
        """
        with self._lock:
            prev = self.current_result
            self.current_result = result
            self.message_count += 1
            self.last_updated = time.time()

            # 计算本轮新填充的槽位
            new_filled = []
            if prev is None:
                new_filled = self._get_all_filled_slots(result)
            else:
                for slot in FIXED_SLOTS:
                    prev_val = getattr(prev, slot, None) or ""
                    curr_val = getattr(result, slot, None) or ""
                    prev_list = prev_val if isinstance(prev_val, list) else [prev_val]
                    curr_list = curr_val if isinstance(curr_val, list) else [curr_val]
                    # 槽位从空变有，或列表从空变有内容
                    if not prev_list or (isinstance(prev_list[0], str) and not prev_list[0].strip()):
                        if curr_list and (isinstance(curr_list[0], str) and curr_list[0].strip() or not isinstance(curr_list[0], str)):
                            new_filled.append(slot)

            return new_filled

    def _get_all_filled_slots(self, result: GpsClarifyResult) -> list[str]:
        """返回当前结果中已填充的槽位列表。"""
        filled = []
        for slot in FIXED_SLOTS:
            val = getattr(result, slot, None)
            if val and (not isinstance(val, str) or val.strip()):
                filled.append(slot)
        return filled

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

    def is_max_reached(self) -> bool:
        """是否已达到最大追问轮次。"""
        with self._lock:
            return self.message_count >= self.MAX_MESSAGE_COUNT

    def get_filled_slots(self) -> list[str]:
        """返回当前已填充的槽位名称列表。"""
        if self.current_result is None:
            return []
        return self._get_all_filled_slots(self.current_result)


# ── 全局会话存储（生产环境应换 Redis）─────────────────────────────────────────

# 内存存储：session_id -> ClarifierSession
_sessions: dict[str, ClarifierSession] = {}
_sessions_lock = threading.Lock()

# 会话超时：超过 SESSION_TTL 秒无活动则清理
SESSION_TTL_SECONDS = 3600  # 1 小时
_MAX_SESSIONS = 1000         # 最多同时 1000 个会话


def get_session(session_id: str) -> Optional[ClarifierSession]:
    """获取已存在的会话，不存在则返回 None。"""
    with _sessions_lock:
        return _sessions.get(session_id)


def get_or_create_session(
    session_id: str,
    initial_result: Optional[GpsClarifyResult] = None,
) -> ClarifierSession:
    """获取已存在的会话或创建新会话（不覆盖已有会话）。"""
    with _sessions_lock:
        if session_id not in _sessions:
            # 简单内存保护：会话过多时清理最早的
            if len(_sessions) >= _MAX_SESSIONS:
                oldest = min(_sessions.items(), key=lambda kv: kv[1].last_updated)
                del _sessions[oldest[0]]
            _sessions[session_id] = ClarifierSession(
                session_id=session_id,
                initial_result=initial_result,
            )
        elif initial_result is not None and _sessions[session_id].current_result is None:
            # 仅当会话存在但尚未有结果时才初始化（首次澄清）
            _sessions[session_id].current_result = initial_result
        return _sessions[session_id]


def create_session(
    session_id: str,
    initial_result: Optional[GpsClarifyResult] = None,
) -> ClarifierSession:
    """强制创建新会话（覆盖已存在的同名会话）。用于重置澄清流程。"""
    with _sessions_lock:
        _sessions[session_id] = ClarifierSession(
            session_id=session_id,
            initial_result=initial_result,
        )
        return _sessions[session_id]


def clear_session(session_id: str) -> None:
    """清除会话（对话结束后调用）。"""
    with _sessions_lock:
        _sessions.pop(session_id, None)


def cleanup_expired_sessions() -> int:
    """清理超时会话，返回清理数量。"""
    now = time.time()
    with _sessions_lock:
        expired = [
            sid for sid, s in _sessions.items()
            if now - s.last_updated > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del _sessions[sid]
        return len(expired)


# ── 公开接口 ───────────────────────────────────────────────────────────────────

async def missing_slots(result: Optional[GpsClarifyResult] = None) -> list[str]:
    """返回缺失的固定槽位名称列表（兼容原占位接口）。"""
    session = ClarifierSession(session_id="_temp", initial_result=result)
    return [ms.slot for ms in session.get_missing_slots()]
