"""Pydantic schemas."""

from app.schemas.gps import (
    ChatMessage,
    ClarifyRequest,
    ClarifyResponse,
    DifficultyLevel,
    GpsClarifyResult,
    MissingSlot,
    SlotUpdate,
    TeachingStyle,
)
from app.schemas.lesson_ir import (
    DagSnapshot,
    DialogueTurn,
    LessonIRCreate,
    LessonIRListResponse,
    LessonIRResponse,
    MaterialBinding,
    TeachingSlots,
)
from app.schemas.materials import ChunkResponse, MaterialDetailResponse, MaterialResponse

__all__ = [
    # materials
    "ChunkResponse",
    "MaterialDetailResponse",
    "MaterialResponse",
    # gps
    "ChatMessage",
    "ClarifyRequest",
    "ClarifyResponse",
    "DifficultyLevel",
    "GpsClarifyResult",
    "MissingSlot",
    "SlotUpdate",
    "TeachingStyle",
    # lesson_ir
    "DagSnapshot",
    "DialogueTurn",
    "LessonIRCreate",
    "LessonIRListResponse",
    "LessonIRResponse",
    "MaterialBinding",
    "TeachingSlots",
]
