"""课堂互动内容契约。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


InteractionType = Literal["choice", "true_false", "fill_blank"]


class InteractiveGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outline: dict
    interaction_type: InteractionType = "choice"
    count: int = Field(default=3, ge=1, le=5)
    section_id: str | None = Field(default=None, max_length=64)


class InteractiveItem(BaseModel):
    id: str
    type: InteractionType
    prompt: str = Field(max_length=500)
    options: list[str] = Field(default_factory=list, max_length=6)
    answer: str = Field(max_length=500)
    explanation: str = Field(max_length=500)


class InteractiveGenerateResponse(BaseModel):
    interaction_type: InteractionType
    items: list[InteractiveItem]
    html: str
    warnings: list[str]
