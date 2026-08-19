"""bge-reranker-v2-m3 重排占位。"""


def rerank(query: str, candidates: list[str], top_k: int = 5) -> list[str]:
    """占位：保留前 top_k 个。"""
    return candidates[:top_k]