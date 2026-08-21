"""Embedding helpers.

The production target is BGE-M3 + pgvector. Until that model is provisioned,
we still expose a deterministic, dependency-free vectorizer so callers can
develop against a stable interface instead of silently receiving all-zero
vectors.
"""

import hashlib
import math
import re


def _terms(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return deterministic hashed vectors for local development.

    This is not a semantic model; it is a stable fallback used until BGE-M3
    is installed. Vectors are L2-normalized and therefore safe for cosine
    similarity tests and future pgvector migration.
    """
    dimension = 256
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
