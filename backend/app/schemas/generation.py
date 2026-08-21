"""Courseware generation task contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pptagent import PptEditAction


class GenerationSection(BaseModel):
    """Bounded outline section accepted by the fixed PPTX renderer."""

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    bullets: list[str] = Field(default_factory=list, max_length=30)
    duration_minutes: int = Field(default=0, ge=0, le=180)
    slide_count: int = Field(default=1, ge=1, le=20)


class GenerationRequest(BaseModel):
    """Validated payload persisted before background rendering starts."""

    title: str = Field(min_length=1, max_length=255)
    subject: str = Field(default="", max_length=128)
    grade: str = Field(default="", max_length=128)
    sections: list[GenerationSection] = Field(min_length=1, max_length=50)
    total_slides: int = Field(default=0, ge=0, le=50)
    total_duration_minutes: int = Field(default=0, ge=0, le=600)
    lesson_id: str = Field(min_length=1, max_length=36)
    actions: list[PptEditAction] = Field(default_factory=list, max_length=30)


class GenerationJobResponse(BaseModel):
    """Canonical generation status used by REST, SSE and the frontend."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str
    lesson_id: str
    job_type: Literal["pptx"]
    status: Literal["queued", "generating", "cancelling", "cancelled", "completed", "failed"]
    progress: int
    task_id: str | None = None
    output: dict[str, Any] | None = None
    error_message: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    updated_at: datetime


class GenerationJobListResponse(BaseModel):
    """Paginated generation history for a lesson or the current teacher."""

    items: list[GenerationJobResponse]
    total: int
    page: int
    page_size: int


class GenerationActionResponse(BaseModel):
    """Small response for cancel/retry actions."""

    job: GenerationJobResponse
    message: str
