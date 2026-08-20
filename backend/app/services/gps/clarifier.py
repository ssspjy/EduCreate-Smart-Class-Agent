"""GPS 多轮澄清服务。

文档 §3.2 services/gps/clarifier.py：
- ClarifierSession 管理一个 GPS 会话的多轮对话上下文
- 每次收到用户输入 → LLM 提取 → 比对缺失槽位 → 生成追问（模板 + LLM 润色）
- 支持材料摘要注入（rag_service）
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Optional

from app.schemas.gps import GpsClarifyResult
from app.services.gps.reasoner import ExtractedIntent, extract_intent

logger = logging.getLogger(__name__)


# ── 固定槽位定义 ───────────────────────────────────────────────────────────────

FIXED_SLOTS = ["subject", "grade", "topic", "objectives", "key_points"]

SLOT_HINTS = {
    "subject": "请问这门课属于哪个科目？",
    "grade": "请问学生是哪个年级？",
    "topic": "请告诉我这门课的主题是什么？",
    "objectives": "还没有告诉我这门课的学习目标，你希望学生学完之后能掌握什么？",
    "key_points": "这门课有哪些核心知识点需要重点讲解？",
}


@dataclass(init=False)
class DialogueEntry:
    """单轮对话记录。"""

    role: str  # user | assistant
    content: str
    timestamp: datetime
    filled_slots: list[str]

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[datetime] = None,
        filled_slots: Optional[list[str]] = None,
        new_filled_slots: Optional[list[str]] = None,
    ) -> None:
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.utcnow()
        self.filled_slots = list(filled_slots if filled_slots is not None else (new_filled_slots or []))

    @property
    def new_filled_slots(self) -> list[str]:
        return self.filled_slots

    @new_filled_slots.setter
    def new_filled_slots(self, value: list[str]) -> None:
        self.filled_slots = list(value)


@dataclass(init=False)
class ClarifierSession:
    """GPS 澄清会话（内存存储，适合开发阶段）。"""

    session_id: str
    lesson_id: str
    # 当前已提取的意图
    intent: ExtractedIntent = field(default_factory=ExtractedIntent)
    # 多轮对话历史
    history: list[DialogueEntry] = field(default_factory=list)
    # 已确认不再追问的槽位（用户明确拒绝回答）
    skipped_slots: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    MAX_MESSAGE_COUNT: ClassVar[int] = 12

    def __init__(
        self,
        session_id: str,
        lesson_id: str = "",
        *,
        current_result: Optional[GpsClarifyResult] = None,
        initial_result: Optional[GpsClarifyResult] = None,
        intent: Optional[ExtractedIntent] = None,
        history: Optional[list[DialogueEntry]] = None,
        skipped_slots: Optional[set[str]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.session_id = session_id
        self.lesson_id = lesson_id
        self.intent = intent or ExtractedIntent()
        self.history = list(history or [])
        self.skipped_slots = set(skipped_slots or set())
        self.created_at = created_at or datetime.utcnow()
        self.message_count = 0
        self._current_result: Optional[GpsClarifyResult] = None

        seed_result = current_result or initial_result
        if seed_result is not None:
            self.update(seed_result)

    # ── 槽位口径与 reasoner 对齐 ─────────────────────────────────────────────

    @staticmethod
    def get_slot_display_name(slot: str) -> str:
        """中文槽位名称（追问话术用）。"""
        return {
            "subject": "科目",
            "grade": "年级",
            "topic": "课题",
            "objectives": "学习目标",
            "key_points": "教学重点",
            "difficulty": "难度",
            "style": "授课风格",
            "activities": "课堂活动",
            "prerequisites": "先备知识",
        }.get(slot, slot)

    def get_missing_slots(self) -> list[dict]:
        """返回当前仍缺失的槽位列表（带原因描述）。

        Returns:
            [{"slot": "grade", "reason": "缺少年级信息"}, ...]
        """
        missing = []
        for slot in FIXED_SLOTS:
            if slot in self.skipped_slots:
                continue
            if slot == "objectives":
                if not self.intent.objectives:
                    missing.append({
                        "slot": slot,
                        "reason": f"还没有告诉我这门课的学习目标，你希望学生学完之后能掌握什么？",
                    })
            elif slot == "key_points":
                if not self.intent.key_points:
                    missing.append({
                        "slot": slot,
                        "reason": f"这门课有哪些核心知识点需要重点讲解？",
                    })
            else:
                val = getattr(self.intent, slot, "")
                if not val:
                    missing.append({
                        "slot": slot,
                        "reason": self._default_reason(slot),
                    })
        return missing

    def _default_reason(self, slot: str) -> str:
        """生成槽位缺失的默认追问话术（模板）。"""
        templates = {
            "subject": "请问这门课属于哪个科目？",
            "grade": "请问学生是哪个年级？",
            "topic": "请告诉我这门课的主题是什么？",
        }
        return templates.get(slot, f"请补充「{self.get_slot_display_name(slot)}」信息。")

    def get_completion_ratio(self) -> float:
        """已填槽位 / 总固定槽位（不含 skipped）。"""
        total = len(FIXED_SLOTS) - len(self.skipped_slots)
        if total <= 0:
            return 1.0
        filled = sum(
            1
            for slot in FIXED_SLOTS
            if slot not in self.skipped_slots
            and (getattr(self.intent, slot, "") or (isinstance(getattr(self.intent, slot, None), list) and getattr(self.intent, slot, None)))
        )
        return round(filled / total, 2)

    # ── 对话轮次计数 ──────────────────────────────────────────────────────

    @property
    def dialogue_count(self) -> int:
        return len([e for e in self.history if e.role == "user"])

    @property
    def current_result(self) -> Optional[GpsClarifyResult]:
        if self._current_result is not None:
            return self._current_result
        if any(
            getattr(self.intent, slot, "") or
            (isinstance(getattr(self.intent, slot, None), list) and getattr(self.intent, slot, None))
            for slot in FIXED_SLOTS
        ):
            return GpsClarifyResult.model_validate(self.intent.to_gps_result())
        return None

    @current_result.setter
    def current_result(self, value: Optional[GpsClarifyResult]) -> None:
        self._current_result = value

    def update(self, result: GpsClarifyResult | ExtractedIntent) -> list[str]:
        """兼容旧测试的更新入口：合并结果并返回新填充槽位。"""
        if isinstance(result, GpsClarifyResult):
            self.current_result = result
            self._merge_gps_result(result)
        else:
            self.current_result = GpsClarifyResult.model_validate(result.to_gps_result())
            self._merge_intent(result)
        self.message_count += 1
        return self.get_filled_slots()

    def get_filled_slots(self) -> list[str]:
        """返回当前已填充的固定槽位。"""
        return [
            slot
            for slot in FIXED_SLOTS
            if (getattr(self.intent, slot, "") or (isinstance(getattr(self.intent, slot, None), list) and getattr(self.intent, slot, None)))
        ]

    def is_complete(self) -> bool:
        return len(self.get_missing_slots()) == 0

    def get_dialogue_entries(self) -> list[DialogueEntry]:
        return list(self.history)

    def add_user_message(self, content: str) -> None:
        self.history.append(DialogueEntry(role="user", content=content))
        self.message_count += 1

    def add_assistant_message(self, content: str, new_filled_slots: Optional[list[str]] = None) -> None:
        self.history.append(
            DialogueEntry(
                role="assistant",
                content=content,
                filled_slots=new_filled_slots or [],
            )
        )
        self.message_count += 1

    def is_max_reached(self) -> bool:
        return self.message_count >= self.MAX_MESSAGE_COUNT

    # ── 处理一轮用户输入 ───────────────────────────────────────────────────

    async def process_turn(
        self,
        user_message: str,
        materials_context: Optional[str] = None,
    ) -> dict:
        """处理一轮用户输入。

        流程：用户消息 → LLM 提取 → 比对缺失槽位 → 追问生成
        """
        # 记录用户发言
        user_entry = DialogueEntry(role="user", content=user_message)
        self.history.append(user_entry)

        # LLM 提取意图
        extracted = await extract_intent(
            query=user_message,
            materials_context=materials_context,
        )
        # 合并到当前意图（已填字段覆盖）
        self._merge_intent(extracted)
        self._current_result = GpsClarifyResult.model_validate(self.intent.to_gps_result())

        missing = self.get_missing_slots()
        needs_more = len(missing) > 0

        # 生成追问话术
        suggestion = self._build_suggestion(missing) if needs_more else None

        # 记录助手发言
        assistant_content = suggestion or "已收集到您的教学意图，可以点击「生成大纲」继续。"
        assistant_entry = DialogueEntry(
            role="assistant",
            content=assistant_content,
            filled_slots=[slot["slot"] for slot in missing],
        )
        self.history.append(assistant_entry)

        logger.info(
            "[Clarifier] session=%s 轮次=%d 缺失=%s 完成度=%.0f%%",
            self.session_id,
            self.dialogue_count,
            [m["slot"] for m in missing],
            self.get_completion_ratio() * 100,
        )

        return {
            "result": self.intent.to_gps_result(),
            "missing_slots": missing,
            "needs_more_info": needs_more,
            "suggestion": suggestion,
            "session_id": self.session_id,
        }

    def _merge_intent(self, new: ExtractedIntent) -> None:
        """将新提取结果合并到当前意图（已有字段不覆盖，保持"最早填入"原则）。"""
        for field_name in ["subject", "grade", "topic"]:
            val = getattr(new, field_name, "")
            if val and not getattr(self.intent, field_name, ""):
                setattr(self.intent, field_name, val)
        # 列表字段合并
        for list_field in ["objectives", "key_points"]:
            new_list: list = getattr(new, list_field, [])
            cur_list: list = getattr(self.intent, list_field, [])
            if new_list and not cur_list:
                setattr(self.intent, list_field, new_list[:3])

    def _merge_gps_result(self, result: GpsClarifyResult) -> None:
        """兼容旧接口的结果合并入口。"""
        for field_name in ["subject", "grade", "topic", "difficulty", "style"]:
            val = getattr(result, field_name, "")
            if val:
                setattr(self.intent, field_name, val)
        for list_field in ["objectives", "key_points"]:
            new_list = list(getattr(result, list_field, []))
            if new_list:
                setattr(self.intent, list_field, new_list[:3])

    def _build_suggestion(self, missing: list[dict]) -> str:
        """从缺失槽位生成追问话术。"""
        if not missing:
            return "好的，信息已经足够，可以生成大纲了。"
        slot = missing[0]
        reason = slot.get("reason", "")
        return reason

    def skip_slot(self, slot: str) -> None:
        """用户明确跳过某槽位。"""
        self.skipped_slots.add(slot)
        logger.info("[Clarifier] session=%s 跳过槽位=%s", self.session_id, slot)

    def to_dag_snapshot(self) -> dict:
        """导出对话快照（存入 LessonIR.dag_snapshot）。"""
        return {
            "turns": [
                {
                    "role": e.role,
                    "content": e.content,
                    "timestamp": e.timestamp.isoformat(),
                    "filled_slots": e.filled_slots,
                }
                for e in self.history
            ]
        }


# ── 内存会话存储（开发阶段）────────────────────────────────────────────────────

_sessions: dict[str, ClarifierSession] = {}


def create_session(lesson_id: str = "", session_id: Optional[str] = None) -> ClarifierSession:
    sid = session_id or str(uuid.uuid4())[:8]
    session = ClarifierSession(session_id=sid, lesson_id=lesson_id)
    _sessions[sid] = session
    if lesson_id:
        _sessions[lesson_id] = session
    return session


def get_session(session_id: str) -> Optional[ClarifierSession]:
    return _sessions.get(session_id)


def get_or_create_session(session_id: Optional[str], lesson_id: str = "") -> ClarifierSession:
    if session_id:
        existing = get_session(session_id)
        if existing:
            return existing
        return create_session(lesson_id, session_id=session_id)
    return create_session(lesson_id)


def clear_session(session_id: str) -> bool:
    session = _sessions.get(session_id)
    if session is not None:
        keys_to_delete = [key for key, value in _sessions.items() if value is session]
        for key in keys_to_delete:
            del _sessions[key]
        return True
    return False
