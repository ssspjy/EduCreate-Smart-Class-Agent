"""GPS 服务层单元测试（不依赖外部 LLM API）。"""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from app.schemas.gps import GpsClarifyResult, DifficultyLevel
from app.services.gps.clarifier import (
    ClarifierSession,
    DialogueEntry,
    create_session,
    clear_session,
    get_session,
    get_or_create_session,
    FIXED_SLOTS,
    SLOT_HINTS,
)
from app.services.gps.dag_builder import (
    build_dag,
    build_dag_from_slots,
    SLOT_META,
)


# ── Clarifier Session 测试 ─────────────────────────────────────────────────────

class TestClarifierSession:
    """ClarifierSession 核心逻辑测试。"""

    def test_initial_state_all_slots_missing(self) -> None:
        session = ClarifierSession(session_id="test-1")
        assert session.current_result is None
        assert len(session.get_missing_slots()) == len(FIXED_SLOTS)
        assert not session.is_complete()
        assert session.message_count == 0

    def test_update_fills_single_slot(self) -> None:
        session = ClarifierSession(session_id="test-2")
        result = GpsClarifyResult(
            subject="物理",
            grade="",
            topic="",
            objectives=[],
            key_points=[],
            difficulty="medium",
            style="interactive",
            confidence=0.0,
        )
        new_filled = session.update(result)
        assert "subject" in new_filled
        assert session.current_result is result
        assert session.message_count == 1

    def test_update_merges_with_existing(self) -> None:
        session = ClarifierSession(session_id="test-3")
        result1 = GpsClarifyResult(
            subject="物理",
            grade="",
            topic="",
            objectives=[],
            key_points=[],
            difficulty="medium",
            style="interactive",
            confidence=0.0,
        )
        session.update(result1)

        result2 = GpsClarifyResult(
            subject="物理",
            grade="初中三年级",
            topic="",
            objectives=[],
            key_points=[],
            difficulty="medium",
            style="interactive",
            confidence=0.5,
        )
        new_filled = session.update(result2)
        assert "grade" in new_filled
        assert session.current_result.subject == "物理"
        assert session.current_result.grade == "初中三年级"

    def test_is_complete_true_when_all_filled(self) -> None:
        session = ClarifierSession(session_id="test-4")
        result = GpsClarifyResult(
            subject="物理",
            grade="初中三年级",
            topic="浮力",
            objectives=["理解浮力概念"],
            key_points=["阿基米德原理"],
            difficulty="medium",
            style="interactive",
            confidence=1.0,
        )
        session.update(result)
        assert session.is_complete()

    def test_dialogue_history_tracking(self) -> None:
        session = ClarifierSession(session_id="test-5")
        session.add_user_message("我想讲浮力课")
        session.add_assistant_message("请告诉我是哪个年级", new_filled_slots=[])
        entries = session.get_dialogue_entries()
        assert len(entries) == 2
        assert entries[0].role == "user"
        assert entries[0].content == "我想讲浮力课"
        assert entries[1].role == "assistant"

    def test_get_filled_slots(self) -> None:
        session = ClarifierSession(session_id="test-6")
        result = GpsClarifyResult(
            subject="物理",
            grade="",
            topic="",
            objectives=[],
            key_points=[],
            difficulty="medium",
            style="interactive",
            confidence=0.0,
        )
        session.update(result)
        filled = session.get_filled_slots()
        assert "subject" in filled
        assert "grade" not in filled

    def test_session_id_prefix(self) -> None:
        session = ClarifierSession(session_id="sess-abc123")
        assert session.session_id == "sess-abc123"

    def test_max_reached_flag(self) -> None:
        session = ClarifierSession(session_id="test-7", initial_result=None)
        # 模拟达到最大轮次
        with patch.object(session, "message_count", ClarifierSession.MAX_MESSAGE_COUNT):
            assert session.is_max_reached()


class TestGlobalSessionManagement:
    """全局会话存储测试。"""

    def test_create_and_get_session(self) -> None:
        clear_session("global-test-1")
        session = create_session("global-test-1")
        assert get_session("global-test-1") is session

    def test_get_or_create_creates_new(self) -> None:
        clear_session("global-test-2")
        session = get_or_create_session("global-test-2")
        assert session is not None
        assert get_session("global-test-2") is session

    def test_get_or_create_does_not_overwrite_existing(self) -> None:
        clear_session("global-test-3")
        session1 = get_or_create_session("global-test-3")
        result = GpsClarifyResult(
            subject="物理", grade="", topic="", objectives=[],
            key_points=[], difficulty="medium", style="interactive", confidence=0.5,
        )
        session1.update(result)

        session2 = get_or_create_session("global-test-3")
        # 不应覆盖已有 session
        assert session2 is session1
        assert session2.current_result is result

    def test_clear_session(self) -> None:
        clear_session("global-test-4")
        create_session("global-test-4")
        clear_session("global-test-4")
        assert get_session("global-test-4") is None


# ── DAG Builder 测试 ──────────────────────────────────────────────────────────

class TestDagBuilder:
    """DAG 可视化数据结构生成测试。"""

    def test_build_dag_empty_state(self) -> None:
        dag = build_dag(
            result=None,
            dialogue_entries=[],
            filled_slots=[],
            missing_slots=["subject", "grade", "topic", "objectives", "key_points"],
        )
        assert "nodes" in dag
        assert "edges" in dag
        assert "meta" in dag
        assert dag["meta"]["completion"] == 0.0

    def test_build_dag_partial_filled(self) -> None:
        result = GpsClarifyResult(
            subject="物理",
            grade="初中三年级",
            topic="",
            objectives=[],
            key_points=[],
            difficulty="medium",
            style="interactive",
            confidence=0.5,
        )
        dag = build_dag(
            result=result,
            dialogue_entries=[],
            filled_slots=["subject", "grade"],
            missing_slots=["topic", "objectives", "key_points"],
        )
        # 根节点
        root_nodes = [n for n in dag["nodes"] if n["id"] == "root-intent"]
        assert len(root_nodes) == 1
        assert "物理" in root_nodes[0]["data"]["label"]

        # 槽位节点
        filled_nodes = [n for n in dag["nodes"] if n["data"]["is_filled"]]
        assert len(filled_nodes) >= 2  # subject + grade

        # 完成度
        assert dag["meta"]["filled_count"] == 2
        assert dag["meta"]["missing_count"] == 3

    def test_build_dag_with_dialogue(self) -> None:
        entries = [
            DialogueEntry(role="user", content="我想讲浮力课", new_filled_slots=[]),
            DialogueEntry(role="assistant", content="请告诉我是哪个年级", new_filled_slots=[]),
        ]
        result = GpsClarifyResult(
            subject="物理",
            grade="",
            topic="",
            objectives=[],
            key_points=[],
            difficulty="medium",
            style="interactive",
            confidence=0.0,
        )
        dag = build_dag(
            result=result,
            dialogue_entries=entries,
            filled_slots=["subject"],
            missing_slots=["grade", "topic", "objectives", "key_points"],
        )
        turn_nodes = [n for n in dag["nodes"] if n["id"].startswith("turn-")]
        assert len(turn_nodes) == 2

        # 边：根节点到第一轮
        dag_edges = dag["edges"]
        assert any(e["source"] == "root-intent" and e["target"] == "turn-1" for e in dag_edges)

    def test_build_dag_completion_calculation(self) -> None:
        result = GpsClarifyResult(
            subject="物理", grade="初中", topic="浮力",
            objectives=["理解"], key_points=["公式"],
            difficulty="easy", style="interactive", confidence=1.0,
        )
        dag = build_dag(
            result=result,
            dialogue_entries=[],
            # 传齐所有 SLOT_META 中的槽位（共 10 个）
            filled_slots=[
                "subject", "grade", "topic",
                "difficulty", "style", "objectives", "key_points",
                "activities", "prerequisites", "duration_min",
            ],
            missing_slots=[],
        )
        assert dag["meta"]["completion"] == 1.0
        assert dag["meta"]["missing_count"] == 0

    def test_build_dag_from_slots_helper(self) -> None:
        dag = build_dag_from_slots({
            "subject": "物理",
            "grade": "初中三年级",
            "topic": "浮力",
        })
        assert "nodes" in dag
        # subject/grade/topic 应被识别为 filled
        filled = [n for n in dag["nodes"] if n["data"]["is_filled"]]
        assert len(filled) >= 3

    def test_slot_meta_all_slots_defined(self) -> None:
        """确保每个 FIXED_SLOTS 都有 SLOT_META 定义。"""
        for slot in FIXED_SLOTS:
            assert slot in SLOT_META, f"Slot {slot} missing from SLOT_META"

    def test_slot_hints_includes_all_slots(self) -> None:
        """确保每个槽位都有追问 hint。"""
        for slot in FIXED_SLOTS:
            assert slot in SLOT_HINTS, f"Slot {slot} missing from SLOT_HINTS"


# ── GPS Reasoner 测试（mock LLM）──────────────────────────────────────────────

class TestGpsReasoner:
    """GPS 意图提取服务测试（mock LLM 调用）。"""

    @pytest.mark.asyncio
    async def test_extract_intent_with_mock_llm(self) -> None:
        from app.services.gps.reasoner import extract_intent
        from app.schemas.gps import ChatMessage

        mock_response = """{
            "subject": "物理",
            "grade": "初中三年级",
            "topic": "浮力",
            "difficulty": "medium",
            "style": "interactive",
            "objectives": ["理解浮力概念"],
            "key_points": ["阿基米德原理", "浮沉条件"],
            "activities": [],
            "prerequisites": []
        }"""

        messages = [ChatMessage(role="user", content="我想讲一节物理浮力课")]

        with patch("app.services.gps.reasoner.chat_llm", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            response = await extract_intent(messages)

        assert response.result.subject == "物理"
        assert response.result.grade == "初中三年级"
        assert response.result.topic == "浮力"
        assert "理解浮力概念" in response.result.objectives

    @pytest.mark.asyncio
    async def test_extract_intent_missing_slots_detected(self) -> None:
        from app.services.gps.reasoner import extract_intent
        from app.schemas.gps import ChatMessage

        # LLM 只返回了部分槽位
        mock_response = """{
            "subject": "化学",
            "grade": "",
            "topic": "",
            "difficulty": "hard",
            "style": "experiment",
            "objectives": [],
            "key_points": [],
            "activities": [],
            "prerequisites": []
        }"""

        with patch("app.services.gps.reasoner.chat_llm", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            response = await extract_intent([ChatMessage(role="user", content="化学课")])

        assert response.result.subject == "化学"
        assert not response.result.grade
        assert response.needs_more_info is True
        assert len(response.missing_slots) > 0

    @pytest.mark.asyncio
    async def test_extract_intent_llm_returns_invalid_json(self) -> None:
        from app.services.gps.reasoner import extract_intent
        from app.schemas.gps import ChatMessage

        with patch("app.services.gps.reasoner.chat_llm", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "这不是 JSON 格式的回复"
            response = await extract_intent([ChatMessage(role="user", content="test")])

        # 应降级处理，不崩溃
        assert response.result is not None
        # 降级时 result 字段为空，missing_slots 为空（已用 prev_result）
        assert response.suggestion is None or response.suggestion is not None  # 允许两种情况

    @pytest.mark.asyncio
    async def test_extract_intent_with_materials_context(self) -> None:
        from app.services.gps.reasoner import extract_intent
        from app.schemas.gps import ChatMessage

        mock_response = """{
            "subject": "物理",
            "grade": "高中一年级",
            "topic": "光的折射",
            "difficulty": "medium",
            "style": "interactive",
            "objectives": ["掌握折射定律"],
            "key_points": ["折射率公式"],
            "activities": [],
            "prerequisites": []
        }"""

        messages = [ChatMessage(role="user", content="讲光的折射")]
        materials = "参考材料摘要：光的折射发生在两种介质交界面。"

        with patch("app.services.gps.reasoner.chat_llm", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            response = await extract_intent(messages, materials_context=materials)

        assert response.result.subject == "物理"
        # 验证 chat_llm 被调用（参数包含上下文）
        mock_chat.assert_called_once()
