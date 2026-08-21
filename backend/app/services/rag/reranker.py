"""Lightweight lexical reranker used before the model-backed reranker."""

import re


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower()))


def rerank(query: str, candidates: list[str], top_k: int = 5) -> list[str]:
    """Rank candidates by token overlap and exact phrase matches."""
    query_terms = _terms(query)
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            (2 if query.lower() in candidate.lower() else 0)
            + len(query_terms & _terms(candidate)),
            len(candidate),
        ),
        reverse=True,
    )
    return ranked[: max(0, top_k)]
