"""Semantic memory: text storage with embedding-based retrieval.

Embeddings are stored as JSON arrays in the `semantic_memory` table. Cosine
similarity is computed in-process with numpy.

Embedding backend selection:
  * If `VOYAGE_API_KEY` is set → Voyage AI `voyage-3.5-lite` (1024-dim).
  * Otherwise → deterministic hash stub (512-dim).

Dimension mismatch between backends is handled at read time — rows with an
embedding vector of the wrong length are skipped instead of raising, so the
system degrades gracefully when the backend swaps.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from core.logging import get_logger
from db import get_provider

log = get_logger(__name__)

_STUB_DIM = 512
_VOYAGE_DIM = 1024
_VOYAGE_MODEL = "voyage-3.5-lite"


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


def _embed(text: str, *, input_type: str = "document") -> list[float]:
    """Pick the best available embedding backend for `text`."""
    return _embed_voyage(text, input_type=input_type) or _embed_stub(text)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import numpy as np
    if len(a) != len(b):
        # Dimension mismatch — skip this row rather than crash.
        return -1.0
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))


class SemanticMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> int:
        embedding = _embed(content, input_type="document")
        return get_provider().semantic_store(
            agent_name=self.agent_name,
            content=content,
            embedding=json.dumps(embedding),
            metadata=json.dumps(metadata or {}),
        )

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        q_emb = _embed(query, input_type="query")
        rows = get_provider().semantic_retrieve(self.agent_name)
        if not rows:
            return []
        scored = []
        for row in rows:
            emb = json.loads(row["embedding"])
            score = _cosine_similarity(q_emb, emb)
            if score < 0:       # dimension mismatch — skip stale rows
                continue
            scored.append({
                "id": row["id"],
                "content": row["content"],
                "score": round(score, 4),
                "metadata": json.loads(row["metadata"]),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        get_provider().semantic_clear(self.agent_name)
