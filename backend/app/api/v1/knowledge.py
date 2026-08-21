"""知识库 / 向量检索 API。

文档 §3.2 API/v1/knowledge.py：知识库 / 向量检索（pgvector）。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.core.security import require_user
from app.rag.retriever import retrieve

router = APIRouter(dependencies=[Depends(require_user)])


class SearchRequest(BaseModel):
    """检索请求。"""

    query: str
    top_k: int = 5
    material_ids: list[str] = []


class SearchHit(BaseModel):
    """检索命中。"""

    content: str
    source: str
    score: float


@router.post("/search", response_model=list[SearchHit], summary="向量 + 全文混合检索")
async def search(req: SearchRequest, db: Session = Depends(get_db)) -> list[SearchHit]:
    """Search parsed material chunks using the current local retriever."""
    hits = await retrieve(db, req.query, min(max(req.top_k, 1), 20), req.material_ids or None)
    return [
        SearchHit(
            content=hit.content,
            source=(f"{hit.source} · 第{hit.page_ref}页" if hit.page_ref else hit.source),
            score=hit.score,
        )
        for hit in hits
    ]
