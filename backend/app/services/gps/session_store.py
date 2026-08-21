"""Database-backed serialization for GPS clarification sessions."""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models import GpsSession
from app.services.gps.clarifier import ClarifierSession, DialogueEntry
from app.services.gps.reasoner import ExtractedIntent
from app.schemas.gps import GpsClarifyResult


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.utcnow()


def serialize_session(session: ClarifierSession) -> dict:
    """Convert in-memory GPS state to JSON-safe data."""
    return {
        "intent": session.intent.model_dump(),
        "history": [
            {
                "role": entry.role,
                "content": entry.content,
                "timestamp": entry.timestamp.isoformat(),
                "filled_slots": entry.filled_slots,
            }
            for entry in session.history
        ],
        "skipped_slots": sorted(session.skipped_slots),
        "message_count": session.message_count,
        "current_result": session.current_result.model_dump() if session.current_result else None,
        "created_at": session.created_at.isoformat(),
    }


def deserialize_session(row: GpsSession) -> ClarifierSession:
    """Restore a clarification session from a database row."""
    state = row.state or {}
    history = [
        DialogueEntry(
            role=str(entry.get("role", "assistant")),
            content=str(entry.get("content", "")),
            timestamp=_parse_datetime(entry.get("timestamp")),
            filled_slots=list(entry.get("filled_slots", [])),
        )
        for entry in state.get("history", [])
    ]
    session = ClarifierSession(
        session_id=row.id,
        lesson_id=row.lesson_id or "",
        intent=ExtractedIntent.model_validate(state.get("intent") or {}),
        history=history,
        skipped_slots=set(state.get("skipped_slots", [])),
        created_at=_parse_datetime(state.get("created_at") or row.created_at),
    )
    session.message_count = int(state.get("message_count", len(history)))
    current_result = state.get("current_result")
    if current_result:
        session.current_result = GpsClarifyResult.model_validate(current_result)
    return session


def load_session(db: Session, session_id: str) -> Optional[ClarifierSession]:
    row = db.get(GpsSession, session_id)
    return deserialize_session(row) if row else None


def load_or_create_session(
    db: Session,
    session_id: Optional[str],
    lesson_id: str = "",
) -> ClarifierSession:
    if session_id:
        existing = load_session(db, session_id)
        if existing:
            return existing
    return ClarifierSession(session_id=session_id or uuid.uuid4().hex[:8], lesson_id=lesson_id)


def save_session(db: Session, session: ClarifierSession) -> None:
    row = db.get(GpsSession, session.session_id)
    now = datetime.utcnow()
    if row is None:
        row = GpsSession(
            id=session.session_id,
            lesson_id=session.lesson_id or None,
            state=serialize_session(session),
            created_at=session.created_at,
            updated_at=now,
        )
        db.add(row)
    else:
        row.lesson_id = session.lesson_id or None
        row.state = serialize_session(session)
        row.updated_at = now
    db.commit()


def delete_session(db: Session, session_id: str) -> bool:
    row = db.get(GpsSession, session_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
