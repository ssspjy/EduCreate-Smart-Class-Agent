"""Material retrieval service with pgvector and lexical fallback."""

from dataclasses import dataclass
import logging
import re

from sqlalchemy.orm import Session

from app.models import Chunk, Material
from app.services.rag.embedder import embed_texts

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A material chunk returned by vector or lexical retrieval."""

    content: str
    source: str
    score: float
    material_id: str = ""
    page_ref: int | None = None


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower()))


async def retrieve(
    db: Session,
    query: str,
    top_k: int = 5,
    material_ids: list[str] | None = None,
) -> list[RetrievedChunk]:
    """Retrieve relevant parsed chunks from uploaded materials."""
    query = query.strip()
    if not query or top_k <= 0:
        return []

    query_terms = _terms(query)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        try:
            vector_hits = _retrieve_vector(db, query, top_k, material_ids)
            if vector_hits:
                return vector_hits
        except Exception:
            logger.exception("pgvector retrieval failed; falling back to lexical retrieval")

    return _retrieve_lexical(db, query, top_k, material_ids, query_terms)


def _retrieve_vector(
    db: Session,
    query: str,
    top_k: int,
    material_ids: list[str] | None,
) -> list[RetrievedChunk]:
    """Retrieve by cosine distance on PostgreSQL pgvector."""
    query_vector = embed_texts([query])[0]
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    statement = db.query(Chunk, Material, distance).join(Material, Material.id == Chunk.material_id)
    statement = statement.filter(Material.status == "parsed", Chunk.embedding.isnot(None))
    if material_ids:
        statement = statement.filter(Chunk.material_id.in_(material_ids))
    rows = statement.order_by(distance).limit(top_k).all()
    return [
        RetrievedChunk(
            content=chunk.content,
            source=material.filename,
            score=max(0.0, min(1.0, 1.0 - float(distance_value))),
            material_id=material.id,
            page_ref=chunk.page_ref,
        )
        for chunk, material, distance_value in rows
    ]


def _retrieve_lexical(
    db: Session,
    query: str,
    top_k: int,
    material_ids: list[str] | None,
    query_terms: set[str],
) -> list[RetrievedChunk]:
    statement = db.query(Chunk, Material).join(Material, Material.id == Chunk.material_id)
    statement = statement.filter(Material.status == "parsed")
    if material_ids:
        statement = statement.filter(Chunk.material_id.in_(material_ids))

    hits: list[RetrievedChunk] = []
    for chunk, material in statement.all():
        content_lower = chunk.content.lower()
        overlap = len(query_terms & _terms(chunk.content))
        phrase_bonus = 2 if query.lower() in content_lower else 0
        score = float(overlap + phrase_bonus)
        if score <= 0:
            continue
        hits.append(
            RetrievedChunk(
                content=chunk.content,
                source=material.filename,
                score=score,
                material_id=material.id,
                page_ref=chunk.page_ref,
            )
        )

    hits.sort(key=lambda hit: (hit.score, len(hit.content)), reverse=True)
    return hits[:top_k]
