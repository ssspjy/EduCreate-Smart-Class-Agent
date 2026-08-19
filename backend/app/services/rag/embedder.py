"""BGE-M3 嵌入占位。

文档 §3.2 services/rag/：BGE-M3 + pgvector + ColPali + 全文 + reranker。
后续集成 FlagEmbedding.BGEM3FlagModel 或 HuggingFace Embeddings。
"""


def embed_texts(texts: list[str]) -> list[list[float]]:
    """占位：返回零向量。"""
    return [[0.0] * 1024 for _ in texts]