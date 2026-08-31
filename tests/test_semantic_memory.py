"""Exercises core.memory.semantic.SemanticMemory's real (non-mocked-at-class-
level) code path against a fake DB provider — offline, no VOYAGE_API_KEY or
network needed. Complements tests/test_memory_tools.py, which mocks
SemanticMemory itself rather than the provider underneath it.
"""

from __future__ import annotations

import json

import pytest


class _FakeVectorProvider:
    """In-memory stand-in for db.base.DBProvider's semantic_* methods.

    Mirrors the real SQL contract (agent-scoped, cosine-ranked, top_k) using
    the pure-Python `_cosine_similarity` helper as a test double for the
    pgvector `<=>` operator.
    """

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self._next_id = 1

    def semantic_store(self, *, agent_name, content, embedding, metadata, embedding_model) -> int:
        row_id = self._next_id
        self._next_id += 1
        self.rows.append({
            "id": row_id,
            "agent_name": agent_name,
            "content": content,
            "embedding": embedding,
            "metadata": metadata,
            "embedding_model": embedding_model,
        })
        return row_id

    def semantic_search(self, agent_name: str, query_embedding: list[float], top_k: int) -> list[dict]:
        from core.memory.semantic import _cosine_similarity

        candidates = [r for r in self.rows if r["agent_name"] == agent_name]
        scored = [
            {
                "id": r["id"],
                "content": r["content"],
                "metadata": r["metadata"],
                "score": _cosine_similarity(query_embedding, r["embedding"]),
            }
            for r in candidates
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def semantic_count(self, agent_name: str) -> int:
        return sum(1 for r in self.rows if r["agent_name"] == agent_name)

    def semantic_clear(self, agent_name: str) -> None:
        self.rows = [r for r in self.rows if r["agent_name"] != agent_name]


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> _FakeVectorProvider:
    provider = _FakeVectorProvider()
    monkeypatch.setattr("core.memory.semantic.get_provider", lambda: provider)
    return provider


def _deterministic_embed(text: str, *, input_type: str = "document") -> list[float]:
    """1024-dim so it looks Voyage-shaped without a network call."""
    base = float(len(text) % 7 + 1)
    return [base] * 1024


@pytest.fixture(autouse=True)
def _mock_voyage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.memory.semantic._embed_voyage", _deterministic_embed)
    monkeypatch.setattr("core.memory.semantic._warned_stub_fallback", False)


def test_store_and_retrieve_round_trip(fake_provider: _FakeVectorProvider) -> None:
    from core.memory.semantic import SemanticMemory

    mem = SemanticMemory("maintenance")
    mem.store("Water lemon trees every 7 days.", metadata={"source": "plant_care"})
    mem.store("Check smoke alarms yearly.", metadata={"source": "checklist"})

    hits = mem.retrieve("lemon trees", top_k=2)
    assert len(hits) == 2
    assert all("content" in h and "score" in h and "metadata" in h for h in hits)


def test_retrieve_scoped_by_agent_name(fake_provider: _FakeVectorProvider) -> None:
    from core.memory.semantic import SemanticMemory

    SemanticMemory("maintenance").store("Prune roses in late winter.")
    SemanticMemory("insights").store("Prune investments in cost line X.")

    hits = SemanticMemory("maintenance").retrieve("prune", top_k=5)
    assert all(h["content"] != "Prune investments in cost line X." for h in hits)


def test_store_tags_embedding_model(fake_provider: _FakeVectorProvider) -> None:
    from core.memory.semantic import SemanticMemory, _VOYAGE_MODEL

    SemanticMemory("asset").store("A checklist item.")
    assert fake_provider.rows[0]["embedding_model"] == _VOYAGE_MODEL


def test_retrieve_short_circuits_on_stub_dimension(
    fake_provider: _FakeVectorProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When Voyage is unavailable, the query embedding is 512-dim and can't
    be compared against the vector(1024) column — retrieve() should return
    [] rather than attempt a mismatched SQL search."""
    from core.memory.semantic import SemanticMemory

    monkeypatch.setattr("core.memory.semantic._embed_voyage", lambda text, **kw: None)
    hits = SemanticMemory("maintenance").retrieve("anything")
    assert hits == []


def test_clear_removes_only_that_agent(fake_provider: _FakeVectorProvider) -> None:
    from core.memory.semantic import SemanticMemory

    SemanticMemory("maintenance").store("a")
    SemanticMemory("insights").store("b")

    SemanticMemory("maintenance").clear()
    assert fake_provider.semantic_count("maintenance") == 0
    assert fake_provider.semantic_count("insights") == 1
