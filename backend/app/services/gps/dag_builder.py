"""GPS DAG 可视化结构构建。

文档 §3.2 services/gps/dag_builder.py：
将 ClarifierSession 的多轮对话 + 槽位状态转换为前端 React Flow 的 nodes/edges 数据。
输出格式与 frontend/src/flow/GpsDag.tsx 的 DagGraph 接口完全对齐。
"""

import math
from typing import Any, Optional

from app.services.gps.clarifier import ClarifierSession, DialogueEntry, FIXED_SLOTS

# ── 布局常量 ───────────────────────────────────────────────────────────────────

_ROOT_X = 0
_ROOT_Y = 0

SLOT_X_LEFT = -200  # 缺失槽位在左侧
SLOT_X_RIGHT = 200  # 已填槽位在右侧
SLOT_Y_STEP = 80  # 槽位垂直间距

DIALOGUE_X_LEFT = -200  # 用户消息在左
DIALOGUE_X_RIGHT = 200  # 助手消息在右
DIALOGUE_Y_BASE = 200  # 对话区域起始 Y
DIALOGUE_Y_STEP = 100  # 对话轮次垂直间距

# 槽位在 DAG 布局中的顺序（决定 Y 坐标）
SLOT_LAYOUT_ORDER = FIXED_SLOTS  # 与 clarifier 保持单一定义源

SLOT_META = {
    "subject": {"label": "科目", "slot_type": "text"},
    "grade": {"label": "年级", "slot_type": "text"},
    "topic": {"label": "课题", "slot_type": "text"},
    "objectives": {"label": "学习目标", "slot_type": "list"},
    "key_points": {"label": "教学重点", "slot_type": "list"},
}


# ── 类型（与前端 DagNodeData / DagGraph 对齐）──────────────────────────────────

class DagNode:
    def __init__(
        self,
        id: str,
        label: str,
        value: str | list[str],
        node_type: str,
        level: int,
        is_filled: bool,
        new_in_round: Optional[int] = None,
        source_turn: int = 0,
        x: float = 0,
        y: float = 0,
    ):
        self.id = id
        self.label = label
        self.value = value
        self.type = node_type
        self.level = level
        self.is_filled = is_filled
        self.new_in_round = new_in_round
        self.source_turn = source_turn
        self.x = x
        self.y = y

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "position": {"x": self.x, "y": self.y},
            "data": {
                "label": self.label,
                "value": self.value,
                "type": self.type,
                "level": self.level,
                "is_filled": self.is_filled,
                "new_in_round": self.new_in_round is not None,
                "source_turn": self.source_turn,
            },
        }


class DagEdge:
    def __init__(
        self,
        id: str,
        source: str,
        target: str,
        label: str = "",
        animated: bool = False,
    ):
        self.id = id
        self.source = source
        self.target = target
        self.label = label
        self.animated = animated

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "animated": self.animated,
        }


# ── 核心构建函数 ───────────────────────────────────────────────────────────────

def _build_dag_for_session(session: ClarifierSession) -> dict:
    """从澄清会话构建完整的 DAG 可视化数据。

    布局规则：
    - 根节点居中顶部（教学意图总入口）
    - 已填槽位 → 右侧（绿色），缺失槽位 → 左侧（灰色虚线）
    - 对话轮次从顶部往下排列，左=用户，右=助手
    - 新填充的槽位节点加 animated 边

    Returns:
        {
            "nodes": [...],
            "edges": [...],
            "meta": {
                "filled_count": int,
                "missing_count": int,
                "total_slots": int,
                "completion": float,   # 0~1
                "dialogue_count": int,
                "dialogue_collapsed": bool,
            }
        }
    """
    nodes: list[DagNode] = []
    edges: list[DagEdge] = []
    node_id_counter = [0]

    def next_id(prefix: str) -> str:
        node_id_counter[0] += 1
        return f"{prefix}_{node_id_counter[0]}"

    # ── 1. 根节点 ──────────────────────────────────────────────────────────
    intent_value = session.intent.topic or "教学意图"
    root = DagNode(
        id="root",
        label="教学意图",
        value=intent_value,
        node_type="root",
        level=0,
        is_filled=True,
        x=_ROOT_X,
        y=_ROOT_Y,
    )
    nodes.append(root)

    # ── 2. 槽位节点 ──────────────────────────────────────────────────────
    missing_slots = session.get_missing_slots()
    missing_set = {m["slot"] for m in missing_slots}
    filled_map: dict[str, str | list[str]] = {
        "subject": session.intent.subject,
        "grade": session.intent.grade,
        "topic": session.intent.topic,
        "objectives": session.intent.objectives,
        "key_points": session.intent.key_points,
    }

    slot_count = len(SLOT_LAYOUT_ORDER)
    total_h = (slot_count - 1) * SLOT_Y_STEP
    start_y = -total_h / 2

    for i, slot in enumerate(SLOT_LAYOUT_ORDER):
        slot_y = start_y + i * SLOT_Y_STEP
        is_filled = bool(filled_map.get(slot))
        display_name = ClarifierSession.get_slot_display_name(slot)
        value = filled_map.get(slot, "")
        is_missing = slot in missing_set

        # 节点 X 位置：已填靠右，缺失靠左
        x = SLOT_X_RIGHT if is_filled else SLOT_X_LEFT

        slot_node = DagNode(
            id=f"slot_{slot}",
            label=display_name,
            value=value if value else "待填写",
            node_type="slot_filled" if is_filled else "slot_missing",
            level=1,
            is_filled=is_filled,
            x=x,
            y=slot_y,
        )
        nodes.append(slot_node)

        # 根节点 → 槽位节点（缺失槽位用虚线，已填用实线）
        edges.append(DagEdge(
            id=next_id("e"),
            source="root",
            target=slot_node.id,
            label="",
            animated=is_missing,
        ))

    # ── 3. 对话节点 ──────────────────────────────────────────────────────
    history = session.history
    if history:
        history_start_y = DIALOGUE_Y_BASE
        user_on_left = True  # 奇数轮=用户左，偶数轮=助手右

        turn_nodes: list[tuple[DagNode, DagNode]] = []  # (user_node, assistant_node) per turn
        prev_user_node_id = None

        for turn_idx, entry in enumerate(history):
            if entry.role == "user":
                user_node = DagNode(
                    id=next_id("du"),
                    label="教师",
                    value=entry.content,
                    node_type="dialogue",
                    level=2,
                    is_filled=True,
                    source_turn=turn_idx,
                    x=DIALOGUE_X_LEFT,
                    y=history_start_y + len(turn_nodes) * DIALOGUE_Y_STEP,
                )
                nodes.append(user_node)

                # 找本轮助手节点（下一个 assistant）
                assistant_node = None
                for j in range(turn_idx + 1, len(history)):
                    if history[j].role == "assistant":
                        a_entry = history[j]
                        assistant_node = DagNode(
                            id=next_id("da"),
                            label="系统",
                            value=a_entry.content,
                            node_type="dialogue",
                            level=2,
                            is_filled=True,
                            source_turn=j,
                            x=DIALOGUE_X_RIGHT,
                            y=history_start_y + len(turn_nodes) * DIALOGUE_Y_STEP,
                        )
                        nodes.append(assistant_node)

                        # 填充了哪些槽位 → 连接到对应槽位节点
                        for fs in a_entry.filled_slots:
                            edges.append(DagEdge(
                                id=next_id("e"),
                                source=assistant_node.id,
                                target=f"slot_{fs}",
                                animated=True,
                            ))
                        break

                turn_nodes.append((user_node, assistant_node))

                # 用户节点 → 助手节点（同一轮）
                if assistant_node:
                    edges.append(DagEdge(
                        id=next_id("e"),
                        source=user_node.id,
                        target=assistant_node.id,
                    ))

                # 连接上一轮的最后一个节点
                if prev_user_node_id and assistant_node:
                    edges.append(DagEdge(
                        id=next_id("e"),
                        source=prev_user_node_id,
                        target=user_node.id,
                        label="下一轮",
                    ))

                prev_user_node_id = user_node.id

    # ── 4. 元信息 ────────────────────────────────────────────────────────
    total_slots = len(SLOT_LAYOUT_ORDER)
    filled_count = sum(1 for s in SLOT_LAYOUT_ORDER if bool(filled_map.get(s)))
    meta = {
        "filled_count": filled_count,
        "missing_count": total_slots - filled_count,
        "total_slots": total_slots,
        "completion": session.get_completion_ratio(),
        "dialogue_count": session.dialogue_count,
        "dialogue_collapsed": session.dialogue_count > 6,
    }

    return {
        "nodes": [n.to_dict() for n in nodes],
        "edges": [e.to_dict() for e in edges],
        "meta": meta,
    }


def _build_legacy_dag(
    result: Any = None,
    dialogue_entries: Optional[list[DialogueEntry]] = None,
    filled_slots: Optional[list[str]] = None,
    missing_slots: Optional[list[str]] = None,
) -> dict:
    """兼容旧测试口径的 DAG 构建。"""
    dialogue_entries = dialogue_entries or []
    filled_slots = filled_slots or []
    missing_slots = missing_slots or []
    all_slots = list(dict.fromkeys([*filled_slots, *missing_slots]))
    nodes: list[dict] = []
    edges: list[dict] = []

    root_value = ""
    if result:
        root_value = getattr(result, "subject", "") or getattr(result, "topic", "")
    root_label = root_value or "教学意图"
    nodes.append({
        "id": "root-intent",
        "type": "root",
        "position": {"x": _ROOT_X, "y": _ROOT_Y},
        "data": {
            "label": root_label,
            "value": root_value or "教学意图",
            "type": "root",
            "level": 0,
            "is_filled": True,
            "new_in_round": False,
            "source_turn": 0,
        },
    })

    for idx, slot in enumerate(all_slots):
        is_filled = slot in filled_slots
        nodes.append({
            "id": f"slot-{slot}",
            "type": "slot_filled" if is_filled else "slot_missing",
            "position": {"x": SLOT_X_RIGHT if is_filled else SLOT_X_LEFT, "y": idx * SLOT_Y_STEP},
            "data": {
                "label": slot,
                "value": getattr(result, slot, "") if result else "",
                "type": "slot_filled" if is_filled else "slot_missing",
                "level": 1,
                "is_filled": is_filled,
                "new_in_round": False,
                "source_turn": 0,
            },
        })
        edges.append({
            "id": f"e_{idx}",
            "source": "root-intent",
            "target": f"slot-{slot}",
            "label": "",
            "animated": not is_filled,
        })

    for idx, entry in enumerate(dialogue_entries):
        nodes.append({
            "id": f"turn-{idx + 1}",
            "type": "dialogue",
            "position": {
                "x": DIALOGUE_X_LEFT if entry.role == "user" else DIALOGUE_X_RIGHT,
                "y": DIALOGUE_Y_BASE + idx * DIALOGUE_Y_STEP,
            },
            "data": {
                "label": "教师" if entry.role == "user" else "系统",
                "value": entry.content,
                "type": "dialogue",
                "level": 2,
                "is_filled": True,
                "new_in_round": False,
                "source_turn": idx,
            },
        })
        if idx == 0:
            edges.append({
                "id": "e_turn_0",
                "source": "root-intent",
                "target": "turn-1",
                "label": "",
                "animated": False,
            })
        elif idx > 0:
            edges.append({
                "id": f"e_turn_{idx}",
                "source": f"turn-{idx}",
                "target": f"turn-{idx + 1}",
                "label": "下一轮",
                "animated": False,
            })

    total_slots = len(all_slots)
    filled_count = len(filled_slots)
    meta = {
        "filled_count": filled_count,
        "missing_count": len(missing_slots),
        "total_slots": total_slots,
        "completion": round(filled_count / total_slots, 2) if total_slots else 0.0,
        "dialogue_count": len([e for e in dialogue_entries if e.role == "user"]),
        "dialogue_collapsed": len([e for e in dialogue_entries if e.role == "user"]) > 6,
    }

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": meta,
    }


def build_dag(*args, **kwargs) -> dict:
    """构建 DAG，兼容当前 session 口径和旧测试口径。"""
    if args and len(args) == 1 and isinstance(args[0], ClarifierSession) and not kwargs:
        return _build_dag_for_session(args[0])

    if args and len(args) == 1 and hasattr(args[0], "intent") and hasattr(args[0], "history") and not kwargs:
        return _build_dag_for_session(args[0])

    if "session" in kwargs:
        return _build_dag_for_session(kwargs["session"])

    return _build_legacy_dag(
        result=kwargs.get("result"),
        dialogue_entries=kwargs.get("dialogue_entries"),
        filled_slots=kwargs.get("filled_slots"),
        missing_slots=kwargs.get("missing_slots"),
    )


def build_dag_from_slots(slots: dict, turns: Optional[list[dict]] = None) -> dict:
    """从 slots dict + 对话历史构建 DAG（不依赖 ClarifierSession）。

    用于从 LessonIR 恢复 DAG 快照。
    """
    # 构造一个临时 session 供 build_dag 使用
    class _FakeSession:
        def __init__(self, slots_dict: dict, turns_list: list):
            from app.services.gps.reasoner import ExtractedIntent
            self.intent = ExtractedIntent()
            self.skipped_slots = set()
            for k, v in slots_dict.items():
                setattr(self.intent, k, v)
            self.history = [
                DialogueEntry(
                    role=t["role"],
                    content=t["content"],
                    timestamp=__import__("datetime").datetime.fromisoformat(t.get("timestamp", "2024-01-01T00:00:00")),
                    filled_slots=t.get("filled_slots", []),
                )
                for t in (turns_list or [])
            ]

        @staticmethod
        def get_slot_display_name(slot):
            return ClarifierSession.get_slot_display_name(slot)

        def get_missing_slots(self):
            return ClarifierSession.get_missing_slots(self)

        @property
        def dialogue_count(self):
            return len([e for e in self.history if e.role == "user"])

        def get_completion_ratio(self):
            return ClarifierSession.get_completion_ratio(self)

    fake_session = _FakeSession(slots, turns or [])
    return build_dag(fake_session)
