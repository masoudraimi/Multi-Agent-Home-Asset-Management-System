"""Semantic memory: text storage with embedding-based retrieval.

Embeddings are stored as JSON arrays in SQLite. Cosine similarity is computed
with numpy (available as a Streamlit/pandas transitive dependency).

The _embed() method uses a deterministic hash-based stub for now (no external
embedding API required). Swap _embed() for Voyage AI or another embeddings
endpoint when a key is available.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent.parent / "data" / "home_assets.db"
EMBEDDING_DIM = 512


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name  TEXT NOT NULL,
            content     TEXT NOT NULL,
            embedding   TEXT NOT NULL,
            metadata    TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)


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
        with sqlite3.connect(DB_PATH) as conn:
            _ensure_table(conn)

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> int:
        embedding = _embed_stub(content)
        with sqlite3.connect(DB_PATH) as conn:
            _ensure_table(conn)
            cur = conn.execute(
                "INSERT INTO semantic_memory (agent_name, content, embedding, metadata) VALUES (?, ?, ?, ?)",
                (self.agent_name, content, json.dumps(embedding), json.dumps(metadata or {})),
            )
            return cur.lastrowid

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        q_emb = _embed_stub(query)
        with sqlite3.connect(DB_PATH) as conn:
            _ensure_table(conn)
            rows = conn.execute(
                "SELECT id, content, embedding, metadata FROM semantic_memory WHERE agent_name=?",
                (self.agent_name,),
            ).fetchall()
        if not rows:
            return []
        scored = []
        for row_id, content, emb_json, meta_json in rows:
            emb = json.loads(emb_json)
            score = _cosine_similarity(q_emb, emb)
            scored.append({
                "id": row_id,
                "content": content,
                "score": round(score, 4),
                "metadata": json.loads(meta_json),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM semantic_memory WHERE agent_name=?", (self.agent_name,))
