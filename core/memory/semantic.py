"""Semantic memory: text storage with embedding-based retrieval.

Embeddings are stored as JSON arrays in the semantic_memory table.
Cosine similarity is computed with numpy.

The _embed() method uses a deterministic hash-based stub for now (no external
embedding API required). Swap _embed() for Voyage AI or another embeddings
endpoint when a key is available.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from db_conn import get_client

EMBEDDING_DIM = 512


def _embed_stub(text: str) -> list[float]:
    """Deterministic hash-based stub embedding. Replace with real API call for production."""
    import numpy as np
    h = int(hashlib.md5(text.encode()).hexdigest(), 16)
    rng = np.random.default_rng(h % (2**32))
    vec = rng.random(EMBEDDING_DIM).astype(float)
    norm = float(np.linalg.norm(vec))
    return (vec / (norm + 1e-9)).tolist()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import numpy as np
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))


class SemanticMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> int:
        embedding = _embed_stub(content)
        result = get_client().table("semantic_memory").insert({
            "agent_name": self.agent_name,
            "content": content,
            "embedding": json.dumps(embedding),
            "metadata": json.dumps(metadata or {}),
        }).execute()
        return result.data[0]["id"]

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        q_emb = _embed_stub(query)
        rows = (
            get_client()
            .table("semantic_memory")
            .select("id, content, embedding, metadata")
            .eq("agent_name", self.agent_name)
            .execute()
            .data
        )
        if not rows:
            return []
        scored = []
        for row in rows:
            emb = json.loads(row["embedding"])
            score = _cosine_similarity(q_emb, emb)
            scored.append({
                "id": row["id"],
                "content": row["content"],
                "score": round(score, 4),
                "metadata": json.loads(row["metadata"]),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        get_client().table("semantic_memory").delete().eq("agent_name", self.agent_name).execute()
