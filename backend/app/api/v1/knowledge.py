"""知识库 / 向量检索 API。

文档 §3.2 API/v1/knowledge.py：知识库 / 向量检索（pgvector）。
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SearchRequest(BaseModel):
    """检索请求。"""

    query: str
    top_k: int = 5


class SearchHit(BaseModel):
    """检索命中。"""

    content: str
    source: str
    score: float


@router.post("/search", response_model=list[SearchHit], summary="向量 + 全文混合检索")
async def search(req: SearchRequest) -> list[SearchHit]:
    """占位：返回空结果，后续接入 BGE-M3 + pgvector。"""
    return []