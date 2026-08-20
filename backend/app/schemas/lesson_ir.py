"""Lesson IR（中间表征）Pydantic schemas。

文档 §3.2 链路核心数据契约：
LessonIR 是 GPS 澄清结果和 PPTAgent 生成之间的唯一数据标准。
所有上游（GPS）和下游（PPTAgent）的数据结构必须与此处对齐。

Schema 设计要点：
- slots: 结构化教学意图（GPS 提取结果）
- dag_snapshot: GPS 多轮对话历史（用于回溯和追问）
- reference_materials: 参考资料绑定（RAG evidence 锚点）
- version: 版本号，每轮修改自增，不覆盖旧版本

枚举类型（DifficultyLevel、TeachingStyle）统一在 gps.py 中定义，
lesson_ir.py 通过 from ..schemas.gps 复用，避免重复定义导致的类型不一致。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.gps import DifficultyLevel, TeachingStyle

# Re-export for backward compatibility in case other modules import from here
__all__ = ["DifficultyLevel", "TeachingStyle"]


class DialogueTurn(BaseModel):
    """GPS 多轮对话中的单轮对话。"""

    role: str = Field(description="角色：user | assistant | system")
    content: str = Field(description="对话内容")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    filled_slots: list[str] = Field(
        default_factory=list,
        description="本轮新填充的槽位名列表",
    )


class MaterialBinding(BaseModel):
    """参考资料与 LessonIR 槽位的绑定记录。"""

    material_id: str = Field(description="参考材料的 ID")
    chunk_ids: list[str] = Field(
        default_factory=list,
        description="引用到的具体 chunk ID 列表",
    )
    bound_slot: str = Field(
        description="绑定到哪个 slot：objectives | key_points | activities | prerequisites | ... "
    )
    excerpt: str = Field(description="引用摘录文本（前 200 字）")
    page_ref: Optional[int] = Field(default=None, description="来源页码（PDF 等）")


class TeachingSlots(BaseModel):
    """GPS 提取的结构化教学意图。"""

    subject: str = Field(default="", description="科目，如：物理、化学、数学")
    grade: str = Field(default="", description="年级，如：初中一年级、高中二年级")
    topic: str = Field(default="", description="课题/主题，如：浮力、光合作用")
    duration_min: int = Field(default=45, description="课时时长（分钟）")
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM,
        description="难度等级：easy | medium | hard",
    )
    style: TeachingStyle = Field(
        default=TeachingStyle.INTERACTIVE,
        description="授课风格：theory | interactive | experiment",
    )
    objectives: list[str] = Field(
        default_factory=list,
        description="学习目标列表，如：理解阿基米德原理",
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="教学重点列表，如：浮力公式 F浮=ρ液gV排",
    )
    activities: list[str] = Field(
        default_factory=list,
        description="课堂活动安排，如：分组实验、小组讨论",
    )
    prerequisites: list[str] = Field(
        default_factory=list,
        description="先备知识要求，如：力的合成与分解",
    )

    model_config = ConfigDict(use_enum_values=True)


class DagSnapshot(BaseModel):
    """GPS 对话 DAG 快照，用于回溯和追问。"""

    turns: list[DialogueTurn] = Field(
        default_factory=list,
        description="对话历史（按时间顺序）",
    )

    def add_turn(self, role: str, content: str, filled_slots: Optional[List[str]] = None) -> None:
        """追加一轮对话。"""
        self.turns.append(
            DialogueTurn(role=role, content=content, filled_slots=filled_slots or [])
        )


# ── Request / Response schemas ────────────────────────────────────────────────

class LessonIRCreate(BaseModel):
    """创建或更新 LessonIR 的请求体。"""

    lesson_id: str = Field(description="所属 lesson 的 ID")
    slots: TeachingSlots = Field(description="GPS 提取的结构化教学意图")
    dag_snapshot: DagSnapshot = Field(default_factory=DagSnapshot, description="GPS 对话历史快照")
    reference_materials: list[MaterialBinding] = Field(
        default_factory=list,
        description="参考资料绑定列表",
    )


class LessonIRResponse(BaseModel):
    """LessonIR 响应体。"""

    id: str
    lesson_id: str
    version: int
    slots: TeachingSlots
    dag_snapshot: DagSnapshot
    reference_materials: list[MaterialBinding]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonIRListResponse(BaseModel):
    """某 lesson 下所有 LessonIR 版本列表。"""

    lesson_id: str
    versions: list[LessonIRResponse] = Field(description="按 version 从大到小排序")
