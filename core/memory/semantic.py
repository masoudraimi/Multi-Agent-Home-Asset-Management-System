"""Semantic memory: text storage with embedding-based retrieval.

Embeddings are stored in a pgvector `vector(1024)` column; similarity search
(`ORDER BY embedding_vec <=> query LIMIT k`) runs in SQL via
`db.*.semantic_search`, not as a Python-side loop over every row.

Embedding backend selection:
  * If `VOYAGE_API_KEY` is set → Voyage AI `voyage-3.5-lite` (1024-dim).
  * Otherwise → deterministic hash stub (512-dim). This is a degraded mode:
    the stub carries no semantic meaning, and a stub-dimensioned vector can't
    be compared against the vector(1024) column at all, so `retrieve()`
    short-circuits to `[]` rather than issuing a meaningless SQL search. The
    fallback is logged loudly (see `_warn_stub_fallback_once`), not silently.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any

from core.logging import get_logger
from db import get_provider

log = get_logger(__name__)

_STUB_DIM = 512
_VOYAGE_DIM = 1024
_VOYAGE_MODEL = "voyage-3.5-lite"
_STUB_MODEL = "hash_stub_v1"

_warned_stub_fallback = False


def _embed_stub(text: str, *, dim: int = _STUB_DIM) -> list[float]:
    """Deterministic hash-based stub — used when no VOYAGE_API_KEY is set."""
    import numpy as np
    h = int(hashlib.md5(text.encode()).hexdigest(), 16)
    rng = np.random.default_rng(h % (2**32))
    vec = rng.random(dim).astype(float)
    norm = float(np.linalg.norm(vec))
    return (vec / (norm + 1e-9)).tolist()


def _embed_voyage(text: str, *, input_type: str = "document") -> list[float] | None:
    """Voyage AI embedding call. Returns None on failure so callers can fall back."""
    api_key = os.environ.get("VOYAGE_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import httpx
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"input": [text], "model": _VOYAGE_MODEL, "input_type": input_type},
            )
            resp.raise_for_status()
            data = resp.json()
        return data["data"][0]["embedding"]
    except Exception:
        log.exception("voyage_embed_failed", model=_VOYAGE_MODEL)
        return None


def _warn_stub_fallback_once() -> None:
    global _warned_stub_fallback
    if _warned_stub_fallback:
        return
    _warned_stub_fallback = True
    banner = (
        "\n" + "!" * 78 + "\n"
        "! SEMANTIC MEMORY IS RUNNING ON THE HASH-STUB EMBEDDING FALLBACK.\n"
        "! VOYAGE_API_KEY is missing or invalid — retrieval quality is\n"
        "! degraded to random noise. Set VOYAGE_API_KEY to restore real RAG.\n"
        + "!" * 78 + "\n"
    )
    print(banner, file=sys.stderr)
    log.warning(
        "semantic_embedding_stub_fallback_active",
        reason="missing_or_invalid_VOYAGE_API_KEY",
        impact="retrieval_quality_degraded_to_random_noise",
    )


def _embed(text: str, *, input_type: str = "document") -> list[float]:
    """Pick the best available embedding backend for `text`."""
    vec = _embed_voyage(text, input_type=input_type)
    if vec is not None:
        return vec
    _warn_stub_fallback_once()
    return _embed_stub(text)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity — used only by the in-memory test double
    in tests/test_semantic_memory.py, not by the production SQL-search path.
    """
    import numpy as np
    if len(a) != len(b):
        return -1.0
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))


class SemanticMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> int:
        embedding = _embed(content, input_type="document")
        model = _VOYAGE_MODEL if len(embedding) == _VOYAGE_DIM else _STUB_MODEL
        return get_provider().semantic_store(
            agent_name=self.agent_name,
            content=content,
            embedding=embedding,
            metadata=json.dumps(metadata or {}),
            embedding_model=model,
        )

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        q_emb = _embed(query, input_type="query")
        if len(q_emb) != _VOYAGE_DIM:
            # Stub-dimensioned query embedding can't be compared against the
            # vector(1024) column — surface an empty result rather than a
            # SQL error. The fallback warning already fired in _embed().
            return []
        rows = get_provider().semantic_search(self.agent_name, q_emb, top_k)
        results = []
        for row in rows:
            meta = row["metadata"]
            results.append({
                "id": row["id"],
                "content": row["content"],
                "score": round(float(row["score"]), 4),
                "metadata": json.loads(meta) if isinstance(meta, str) else (meta or {}),
            })
        return results

    def clear(self) -> None:
        get_provider().semantic_clear(self.agent_name)
