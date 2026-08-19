"""RAG 检索模块占位。"""

from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    """检索到的知识块（占位）。"""

    content: str
    source: str
    score: float


async def retrieve(query: str, top_k: int = 5) -> list[RetrievedChunk]:
    """占位检索函数，后续接入 BGE-M3 + pgvector。"""
    return []