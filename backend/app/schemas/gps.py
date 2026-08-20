"""GPS 教学意图澄清 Pydantic schemas。

文档 §3.2 services/gps/：GPS Schema 统一入口。

消除三处重复定义：
- frontend/src/services/api.ts          → GpsClarifyResult
- backend/app/api/v1/gps.py            → ClarifyRequest, GpsResult
- backend/app/api/v1/lessons.py        → GpsResult

所有 GPS 相关类型统一在此文件定义，其他文件 import。
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    """难度等级（与 lesson_ir.py 保持一致）。

    唯一定义源，所有模块从此处 import。
    """

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TeachingStyle(str, Enum):
    """授课风格（唯一定义源，所有模块从此处 import）。"""

    THEORY = "theory"       # 理论为主
    INTERACTIVE = "interactive"  # 互动为主
    EXPERIMENT = "experiment"   # 实验为主


class ChatMessage(BaseModel):
    """对话消息。"""

    role: str = Field(description="角色：user | assistant | system")
    content: str = Field(description="消息内容")


class ClarifyRequest(BaseModel):
    """GPS 澄清请求（首次或继续多轮对话）。

    与原 backend/app/api/v1/gps.py ClarifyRequest 合并。
    """

    query: Optional[str] = Field(default=None, description="本轮用户输入（首次调用必填）")
    messages: Optional[list[ChatMessage]] = Field(
        default=None,
        description="多轮对话历史（首次调用可不传）",
    )
    materials: list[str] = Field(
        default_factory=list,
        description="已上传参考材料的 ID 列表",
    )
    lesson_id: Optional[str] = Field(
        default=None,
        description="关联的 lesson workspace ID（用于绑定材料）",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="澄清会话 ID（用于多轮对话状态追踪，不传则自动生成）",
    )


class GpsClarifyResult(BaseModel):
    """GPS 结构化提取结果（与前端 api.ts GpsClarifyResult 完全对齐）。

    与原 backend/app/api/v1/gps.py GpsResult 合并。
    相比原 gps.py，新增了 style 和 confidence 字段。
    """

    subject: str = Field(default="", description="科目")
    grade: str = Field(default="", description="年级")
    topic: str = Field(default="", description="课题/主题")
    objectives: list[str] = Field(default_factory=list, description="学习目标")
    key_points: list[str] = Field(default_factory=list, description="教学重点")
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM,
        description="难度等级：easy | medium | hard",
    )
    style: str = Field(
        default="interactive",
        description="授课风格：theory | interactive | experiment",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="GPS 置信度（0~1），低于阈值时系统应追问",
    )

    model_config = {"use_enum_values": True}


class MissingSlot(BaseModel):
    """缺失槽位信息（用于引导追问）。"""

    slot: str = Field(description="槽位名称：subject | grade | topic | objectives | ...")
    reason: str = Field(
        description="缺失原因描述，供前端生成追问话术",
    )


class ClarifyResponse(BaseModel):
    """GPS 澄清完整响应。"""

    result: GpsClarifyResult = Field(description="当前轮提取的结构化结果")
    missing_slots: list[MissingSlot] = Field(
        default_factory=list,
        description="当前仍缺失的槽位列表（空表示完成）",
    )
    needs_more_info: bool = Field(
        default=False,
        description="是否需要继续追问",
    )
    suggestion: Optional[str] = Field(
        default=None,
        description="追问建议话术（当 needs_more_info=True 时返回）",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="澄清会话 ID（前端应持久化到 store，下次请求传入以恢复上下文）",
    )


class SlotUpdate(BaseModel):
    """槽位更新（用于多轮对话中逐步填充）。"""

    slot_name: str
    value: Union[str, list[str]]
