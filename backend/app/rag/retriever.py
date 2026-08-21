"""Material retrieval service.

Uses a lexical score today so the application works without downloading a
large embedding model. The returned shape is intentionally compatible with a
future pgvector-backed implementation.
"""

from dataclasses import dataclass
import re

from sqlalchemy.orm import Session

from app.models import Chunk, Material


@dataclass
class RetrievedChunk:
    """检索到的知识块（占位）。"""

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

    statement = db.query(Chunk, Material).join(Material, Material.id == Chunk.material_id)
    statement = statement.filter(Material.status == "parsed")
    if material_ids:
        statement = statement.filter(Chunk.material_id.in_(material_ids))

    query_terms = _terms(query)
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
