"""Embedding helpers.

The production target is BGE-M3 + pgvector. Until that model is provisioned,
we still expose a deterministic, dependency-free vectorizer so callers can
develop against a stable interface instead of silently receiving all-zero
vectors.
"""

import hashlib
import logging
import math
import re
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)
VECTOR_DIMENSION = 1024


def _terms(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return BGE-M3 vectors when enabled, otherwise deterministic hash vectors.

    ``EMBEDDING_PROVIDER=bge`` is intentionally optional because the model is
    large. If FlagEmbedding is unavailable, the application logs one warning
    and falls back to a stable local vector instead of failing uploads.
    """
    if not texts:
        return []
    settings = get_settings()
    if settings.embedding_provider.lower() == "bge":
        bge_vectors = _embed_with_bge(texts)
        if bge_vectors is not None:
            return bge_vectors

    dimension = VECTOR_DIMENSION
    if settings.embedding_dimension != VECTOR_DIMENSION:
        logger.warning("EMBEDDING_DIMENSION=%s is unsupported by the current schema; using %s", settings.embedding_dimension, VECTOR_DIMENSION)
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * dimension
        for term in _terms(text):
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        vectors.append([value / norm for value in vector] if norm else vector)
    return vectors


@lru_cache(maxsize=1)
def _get_bge_model():
    from FlagEmbedding import BGEM3FlagModel

    settings = get_settings()
    return BGEM3FlagModel(settings.bge_model_name, use_fp16=True)


def _embed_with_bge(texts: list[str]) -> list[list[float]] | None:
    try:
        model = _get_bge_model()
        encoded = model.encode(texts, batch_size=32, max_length=8192)
        dense_vectors = encoded["dense_vecs"]
        dimension = VECTOR_DIMENSION
        result: list[list[float]] = []
        for vector in dense_vectors:
            values = [float(value) for value in vector[:dimension]]
            if len(values) < dimension:
                values.extend([0.0] * (dimension - len(values)))
            norm = math.sqrt(sum(value * value for value in values))
            result.append([value / norm for value in values] if norm else values)
        return result
    except ImportError:
        logger.warning("BGE-M3 provider requested but FlagEmbedding is not installed; using hash embeddings")
    except Exception:
        logger.exception("BGE-M3 embedding failed; using hash embeddings")
    return None
