"""GPS DAG 可视化构建器（展示用，非训练）。

文档 §4.5 DAG 快照设计：
- 根据当前 GPS 会话状态，生成前端 React Flow 可消费的节点/边结构
- 节点类型：root（根节点）/ slot_filled（已填充槽位）/ slot_missing（未填槽位）/ dialogue（对话轮次）
- 边类型：has_child（含子节点）/ filled_from（由某对话轮次填充）/ depends_on（依赖关系）

节点布局策略：采用固定层级布局，确保 DAG 始终可读：
- Level 0：根节点（教学意图）
- Level 1：核心槽位（subject / grade / topic）
- Level 2：扩展槽位（objectives / key_points / difficulty / style）
- Level 3：补充槽位（activities / prerequisites）
- 底部：对话历史节点（按时间顺序排列）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ── 数据类型 ─────────────────────────────────────────────────────────────────

@dataclass
class DagNode:
    """DAG 节点。"""

    id: str
    type: str          # "root" | "slot_filled" | "slot_missing" | "dialogue"
    label: str
    value: str | list[str]  # 槽位值（列表用于 objectives/key_points 等多值槽位）
    level: int         # 层级（0=根，1=核心，2=扩展，3=补充）
    is_filled: bool
    new_in_round: bool = False  # 本轮新填充
    source_turn: int = 0  # 来源对话轮次序号


@dataclass
class DagEdge:
    """DAG 边。"""

    id: str
    source: str
    target: str
    label: str = ""
    animated: bool = False  # 新填充槽位的边带动画


# ── 槽位元信息 ────────────────────────────────────────────────────────────────

SLOT_META: dict[str, dict[str, Any]] = {
    "subject":       {"label": "科目",         "level": 1, "is_core": True},
    "grade":         {"label": "年级",          "level": 1, "is_core": True},
    "topic":         {"label": "课题",          "level": 1, "is_core": True},
    "difficulty":    {"label": "难度",          "level": 2, "is_core": False},
    "style":         {"label": "授课风格",      "level": 2, "is_core": False},
    "objectives":    {"label": "学习目标",      "level": 2, "is_core": False},
    "key_points":    {"label": "教学重点",      "level": 2, "is_core": False},
    "activities":    {"label": "课堂活动",      "level": 3, "is_core": False},
    "prerequisites": {"label": "先备知识",      "level": 3, "is_core": False},
    "duration_min":  {"label": "课时时长",      "level": 3, "is_core": False},
}

# 对话节点最大显示数量（超出时折叠）
MAX_DIALOGUE_NODES = 8


# ── 布局辅助 ────────────────────────────────────────────────────────────────

def _slot_x(level: int, index: int, total: int) -> float:
    """计算槽位节点的 X 坐标（居中布局）。"""
    if total <= 1:
        return 0.0
    spacing = 250.0
    start = -((total - 1) * spacing) / 2
    return start + index * spacing


def _dialogue_x(turn_index: int, total: int) -> float:
    """计算对话节点的 X 坐标。"""
    if total <= 1:
        return 0.0
    spacing = 300.0
    start = -((total - 1) * spacing) / 2
    return start + turn_index * spacing


# ── 核心构建函数 ─────────────────────────────────────────────────────────────

def build_dag(
    result: Any,                          # GpsClarifyResult | None
    dialogue_entries: list[Any],          # list[DialogueEntry]
    filled_slots: list[str],
    missing_slots: list[str],
) -> dict[str, Any]:
    """构建 DAG 可视化数据结构。

    Args:
        result: 当前 GpsClarifyResult（可为 None）
        dialogue_entries: 对话历史列表（DialogueEntry 实例列表）
        filled_slots: 已填充的槽位名称列表
        missing_slots: 仍未填充的槽位名称列表

    Returns:
        {
            "nodes": [...],    # React Flow 节点列表
            "edges": [...],    # React Flow 边列表
            "meta": {
                "filled_count": int,
                "missing_count": int,
                "total_slots": int,
                "completion": float,   # 完成度 0~1
            }
        }
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()

    def add_node(n: DagNode) -> None:
        if n.id in node_ids:
            return
        node_ids.add(n.id)
        # 计算位置
        level_nodes = [x for x in nodes if x.get("data", {}).get("level") == n.level]
        level_idx = len(level_nodes)

        if n.type == "root":
            pos = {"x": 0, "y": 0}
        elif n.type == "dialogue":
            pos = {"x": _dialogue_x(level_idx, len(dialogue_entries)), "y": 450}
        else:
            # 按槽位层级分组
            same_level = [x for x in nodes if x.get("data", {}).get("level") == n.level and x.get("data", {}).get("type") != "root"]
            idx = len(same_level)
            pos = {"x": _slot_x(n.level, idx, len([x for x in nodes if x.get("data", {}).get("level") == n.level]) + 1 or 1), "y": 100 + n.level * 90}

        nodes.append({
            "id": n.id,
            "type": n.type,
            "position": pos,
            "data": {
                "label": n.label,
                "value": n.value,
                "type": n.type,
                "level": n.level,
                "is_filled": n.is_filled,
                "new_in_round": n.new_in_round,
                "source_turn": n.source_turn,
            },
            "style": _node_style(n),
        })

    def add_edge(e: DagEdge) -> None:
        edges.append({
            "id": e.id,
            "source": e.source,
            "target": e.target,
            "label": e.label,
            "animated": e.animated,
            "style": {"stroke": "#52c41a" if e.animated else "#bfbfbf", "strokeWidth": 2},
        })

    # ── Level 0: 根节点 ────────────────────────────────────────────────────
    root_id = "root-intent"
    root_label = f"{result.subject} · {result.grade} · {result.topic}" if result else "教学意图"
    add_node(DagNode(
        id=root_id,
        type="root",
        label=root_label,
        value=root_label,
        level=0,
        is_filled=bool(result and (result.subject or result.grade or result.topic)),
        new_in_round=False,
    ))

    # ── Level 1–3: 槽位节点 ─────────────────────────────────────────────────
    all_slots = set(filled_slots) | set(missing_slots)
    # 按 level 排序
    sorted_slots = sorted(all_slots, key=lambda s: SLOT_META.get(s, {}).get("level", 99))

    for slot in sorted_slots:
        meta = SLOT_META.get(slot, {"label": slot, "level": 3, "is_core": False})
        is_filled = slot in filled_slots
        new_in_round = False  # 已在 clarifier 层计算，这里不重复

        # 取槽位值
        if result is not None and hasattr(result, slot):
            val = getattr(result, slot, None)
            if val is None:
                val = ""
        else:
            val = ""

        node_id = f"slot-{slot}"
        add_node(DagNode(
            id=node_id,
            type="slot_filled" if is_filled else "slot_missing",
            label=meta["label"],
            value=val,
            level=meta["level"],
            is_filled=is_filled,
            new_in_round=new_in_round,
        ))
        # 连接到根节点
        add_edge(DagEdge(
            id=f"edge-{root_id}-{node_id}",
            source=root_id,
            target=node_id,
            label="包含",
            animated=False,
        ))

    # ── 对话历史节点（底部）──────────────────────────────────────────────────
    # 分类：显示最近 MAX_DIALOGUE_NODES 条，超过则折叠
    visible_turns = dialogue_entries[-MAX_DIALOGUE_NODES:] if len(dialogue_entries) > MAX_DIALOGUE_NODES else dialogue_entries
    start_turn = len(dialogue_entries) - len(visible_turns)

    for idx, entry in enumerate(visible_turns):
        turn_num = start_turn + idx + 1
        node_id = f"turn-{turn_num}"
        label = "教师" if entry.role == "user" else "助手"
        content = entry.content[:60] + ("…" if len(entry.content) > 60 else "")
        new_slots_str = "；".join(entry.new_filled_slots) if entry.new_filled_slots else ""

        add_node(DagNode(
            id=node_id,
            type="dialogue",
            label=f"第{turn_num}轮 · {label}",
            value=content,
            level=4,
            is_filled=True,
            new_in_round=False,
            source_turn=turn_num,
        ))

        if idx == 0:
            # 第一条对话连到根节点
            add_edge(DagEdge(
                id=f"edge-{root_id}-{node_id}",
                source=root_id,
                target=node_id,
                label="对话开始",
                animated=False,
            ))
        else:
            # 后续对话连到上一轮
            prev_id = f"turn-{start_turn + idx}"
            add_edge(DagEdge(
                id=f"edge-{prev_id}-{node_id}",
                source=prev_id,
                target=node_id,
                label="",
                animated=False,
            ))

        # 如果本轮有新填充的槽位，连接到对应槽位节点
        if entry.new_filled_slots:
            for slot in entry.new_filled_slots:
                slot_node_id = f"slot-{slot}"
                if slot_node_id in node_ids:
                    add_edge(DagEdge(
                        id=f"edge-{node_id}-{slot_node_id}",
                        source=node_id,
                        target=slot_node_id,
                        label="填充",
                        animated=True,
                    ))

    # ── 完成度元信息 ───────────────────────────────────────────────────────
    total_slots = len(SLOT_META)
    filled_count = len(filled_slots)
    completion = filled_count / total_slots if total_slots > 0 else 0.0

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "filled_count": filled_count,
            "missing_count": len(missing_slots),
            "total_slots": total_slots,
            "completion": round(completion, 2),
            "dialogue_count": len(dialogue_entries),
            "dialogue_collapsed": len(dialogue_entries) > MAX_DIALOGUE_NODES,
        },
    }


def _node_style(n: DagNode) -> dict[str, Any]:
    """根据节点状态生成样式。"""
    if n.type == "root":
        return {
            "border": "2px solid #1890ff",
            "borderRadius": "8px",
            "background": "#e6f7ff",
            "padding": "12px 16px",
            "minWidth": "180px",
            "textAlign": "center",
        }
    if n.type == "slot_filled":
        return {
            "border": "2px solid #52c41a",
            "borderRadius": "6px",
            "background": "#f6ffed",
            "padding": "8px 12px",
            "minWidth": "140px",
            "textAlign": "center",
        }
    if n.type == "slot_missing":
        return {
            "border": "2px dashed #d9d9d9",
            "borderRadius": "6px",
            "background": "#fafafa",
            "padding": "8px 12px",
            "minWidth": "140px",
            "textAlign": "center",
            "color": "#999",
        }
    # dialogue
    if n.label.startswith("教师"):
        return {
            "border": "2px solid #1890ff",
            "borderRadius": "6px",
            "background": "#e6f7ff",
            "padding": "8px 12px",
            "minWidth": "160px",
            "textAlign": "left",
        }
    return {
        "border": "2px solid #52c41a",
        "borderRadius": "6px",
        "background": "#f6ffed",
        "padding": "8px 12px",
        "minWidth": "160px",
        "textAlign": "left",
    }


def build_dag_from_slots(slots: dict[str, Any]) -> dict[str, Any]:
    """从纯槽位字典快速构建 DAG（用于预览/调试，不需要完整会话）。"""
    filled = [k for k, v in slots.items() if v and (not isinstance(v, list) or v)]
    missing = [k for k in SLOT_META if k not in filled]
    return build_dag(
        result=type("GpsResult", (), slots)(),  # 构造临时对象
        dialogue_entries=[],
        filled_slots=filled,
        missing_slots=missing,
    )
