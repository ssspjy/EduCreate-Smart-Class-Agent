"""PPTAgent 参考分析与结构化编辑动作契约。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PptReferenceAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_id: str = Field(min_length=1, max_length=64)


class PptEditAction(BaseModel):
    """仅允许后端固定执行器支持的动作，不接受代码或路径。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "move_section",
        "rename_section",
        "replace_bullet",
        "append_bullet",
        "remove_bullet",
        "set_style",
    ]
    section_id: str | None = Field(default=None, max_length=64)
    to_index: int | None = Field(default=None, ge=0, le=99)
    bullet_index: int | None = Field(default=None, ge=0, le=99)
    title: str | None = Field(default=None, max_length=120)
    text: str | None = Field(default=None, max_length=500)
    style: Literal["classic", "modern", "minimal"] | None = None


class PptAgentApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outline: dict
    actions: list[PptEditAction] = Field(default_factory=list, max_length=30)
    lesson_id: str | None = Field(default=None, max_length=64)
    instruction: str | None = Field(default=None, max_length=500)


class PptAgentApplyResponse(BaseModel):
    outline: dict
    applied: list[dict]
    warnings: list[str]
    edit_request_id: str | None = None


class PptAgentRewriteRequest(BaseModel):
    """教师自然语言意见，先改写为动作，不直接执行。"""

    model_config = ConfigDict(extra="forbid")
    outline: dict
    instruction: str = Field(min_length=1, max_length=500)


class PptAgentRewriteResponse(BaseModel):
    actions: list[PptEditAction]
    warnings: list[str]
    confidence: float = Field(ge=0, le=1)
    explanation: str
