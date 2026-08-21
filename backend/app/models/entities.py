"""Core persistence models for the runnable skeleton."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db.session import Base


def new_id() -> str:
    """Return a stable string UUID for API-facing identifiers."""
    return str(uuid4())


class Material(Base):
    """Uploaded teaching reference material."""

    __tablename__ = "materials"

    id = Column(String(36), primary_key=True, default=new_id)
    filename = Column(String(255), nullable=False)
    mime = Column(String(127), nullable=False, default="application/octet-stream")
    extension = Column(String(16), nullable=False, index=True)
    size = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="uploaded", index=True)
    parse_progress = Column(Integer, nullable=False, default=0)
    task_id = Column(String(255), nullable=True, index=True)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    storage_path = Column(String(1024), nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    parsed_at = Column(DateTime, nullable=True)

    chunks = relationship(
        "Chunk",
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )


class Chunk(Base):
    """Parsed searchable fragment from a material."""

    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=new_id)
    material_id = Column(String(36), ForeignKey("materials.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_ref = Column(Integer, nullable=True)
    bbox = Column(JSON, nullable=True)
    media_ref = Column(String(1024), nullable=True)
    modality = Column(String(32), nullable=False, default="text")
    token_count = Column(Integer, nullable=False, default=0)
    embedding = Column(Vector(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    material = relationship("Material", back_populates="chunks")


class GpsSession(Base):
    """Persisted GPS clarification session state."""

    __tablename__ = "gps_sessions"

    id = Column(String(64), primary_key=True)
    lesson_id = Column(String(36), ForeignKey("lessons.id"), nullable=True, index=True)
    state = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Lesson(Base):
    """Lesson workspace owned by a teacher."""

    __tablename__ = "lessons"

    id = Column(String(36), primary_key=True, default=new_id)
    teacher_id = Column(String(64), nullable=False, default="demo-teacher", index=True)
    title = Column(String(255), nullable=False)
    subject = Column(String(128), nullable=True)
    grade = Column(String(128), nullable=True)
    topic = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="draft", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class LessonIR(Base):
    """Versioned intermediate representation connecting GPS and PPTAgent."""

    __tablename__ = "lesson_irs"

    id = Column(String(36), primary_key=True, default=new_id)
    lesson_id = Column(String(36), ForeignKey("lessons.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    slots = Column(JSON, nullable=False, default=dict)
    dag_snapshot = Column(JSON, nullable=False, default=dict)
    reference_materials = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class GenerationJob(Base):
    """Async generation job placeholder."""

    __tablename__ = "generation_jobs"

    id = Column(String(36), primary_key=True, default=new_id)
    lesson_id = Column(String(36), ForeignKey("lessons.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    output_json = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class GeneratedArtifact(Base):
    """Generated export artifact metadata."""

    __tablename__ = "generated_artifacts"

    id = Column(String(36), primary_key=True, default=new_id)
    job_id = Column(String(36), ForeignKey("generation_jobs.id"), nullable=True, index=True)
    lesson_id = Column(String(36), ForeignKey("lessons.id"), nullable=True, index=True)
    type = Column(String(32), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    storage_path = Column(String(1024), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EditRequest(Base):
    """Teacher edit request rewritten into structured actions."""

    __tablename__ = "edit_requests"

    id = Column(String(36), primary_key=True, default=new_id)
    lesson_id = Column(String(36), ForeignKey("lessons.id"), nullable=False, index=True)
    instruction = Column(Text, nullable=False)
    target_page = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    action_json = Column(JSON, nullable=True)
    from_artifact_id = Column(String(36), ForeignKey("generated_artifacts.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class RagEvidence(Base):
    """Explicit binding between generated content and reference material chunks."""

    __tablename__ = "rag_evidences"

    id = Column(String(36), primary_key=True, default=new_id)
    lesson_ir_id = Column(String(36), ForeignKey("lesson_irs.id"), nullable=False, index=True)
    material_id = Column(String(36), ForeignKey("materials.id"), nullable=False, index=True)
    page_ref = Column(Integer, nullable=True)
    bbox = Column(JSON, nullable=True)
    excerpt = Column(Text, nullable=False)
    usage = Column(String(64), nullable=False, default="outline")
    slot_binding = Column(String(255), nullable=True)
