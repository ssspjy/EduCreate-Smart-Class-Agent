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
from app.schemas.pptagent import PptAgentApplyRequest, PptAgentApplyResponse, PptAgentRewriteRequest, PptAgentRewriteResponse, PptEditAction, PptReferenceAnalyzeRequest
from app.schemas.interactive import InteractiveGenerateRequest, InteractiveGenerateResponse, InteractiveItem

__all__ = [
    # materials
    "ChunkResponse",
    "MaterialDetailResponse",
    "MaterialResponse",
    "PptAgentApplyRequest",
    "PptAgentApplyResponse",
    "PptAgentRewriteRequest",
    "PptAgentRewriteResponse",
    "PptEditAction",
    "PptReferenceAnalyzeRequest",
    "InteractiveGenerateRequest",
    "InteractiveGenerateResponse",
    "InteractiveItem",
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
