"""Phase 5 tests: memory tools (recall_knowledge, remember_fact, recall_facts).

Uses in-memory stubs for the DB provider and SemanticMemory so the tests
run offline and deterministically. Voyage AI is not exercised — its fallback
to the hash stub is tested implicitly (no VOYAGE_API_KEY in the test env).
"""

from __future__ import annotations

from typing import Any

import pytest

from core.session import set_current_user


class _FakeSemanticMemory:
    """In-memory SemanticMemory replacement, keyed by agent_name."""

    _store: dict[str, list[dict]] = {}

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        _FakeSemanticMemory._store.setdefault(agent_name, [])

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> int:
        entries = _FakeSemanticMemory._store[self.agent_name]
        entries.append({"id": len(entries) + 1, "content": content, "metadata": metadata or {}, "score": 0.9})
        return len(entries)

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        entries = _FakeSemanticMemory._store.get(self.agent_name, [])
        # Rank by naive substring match; deterministic and offline
        scored = []
        for e in entries:
            score = 1.0 if query.lower() in e["content"].lower() else 0.1
            scored.append({**e, "score": round(score, 4)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    @classmethod
    def reset(cls) -> None:
        cls._store = {}


class _FakeLongTermMemory:
    """In-memory KV replacement scoped per (agent_name, current user)."""

    _store: dict[tuple[str, str], dict[str, Any]] = {}

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    def _key(self) -> tuple[str, str]:
        from core.session import get_current_user_id
        return (self.agent_name, get_current_user_id())

    def set(self, key: str, value: Any) -> None:
        _FakeLongTermMemory._store.setdefault(self._key(), {})[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return _FakeLongTermMemory._store.get(self._key(), {}).get(key, default)

    def get_all(self) -> dict[str, Any]:
        return dict(_FakeLongTermMemory._store.get(self._key(), {}))

    def delete(self, key: str) -> None:
        _FakeLongTermMemory._store.get(self._key(), {}).pop(key, None)

    @classmethod
    def reset(cls) -> None:
        cls._store = {}


@pytest.fixture(autouse=True)
def _isolate_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset in-memory stores and patch imports before each test."""
    _FakeSemanticMemory.reset()
    _FakeLongTermMemory.reset()
    set_current_user("test-user")
    monkeypatch.setattr("core.memory.semantic.SemanticMemory", _FakeSemanticMemory)
    monkeypatch.setattr("core.memory.long_term.LongTermMemory", _FakeLongTermMemory)


def test_remember_fact_and_recall_facts_round_trip() -> None:
    from tools.langchain_tools import remember_fact, recall_facts

    result = remember_fact.invoke({
        "key": "preferred_units",
        "value": "metric",
        "category": "preference",
    })
    assert result["status"] == "stored"
    assert result["key"] == "preferred_units"

    facts = recall_facts.invoke({})
    assert facts["count"] == 1
    assert facts["facts"]["preferred_units"]["value"] == "metric"
    assert facts["facts"]["preferred_units"]["category"] == "preference"


def test_recall_facts_pattern_filter() -> None:
    from tools.langchain_tools import remember_fact, recall_facts

    remember_fact.invoke({"key": "timezone", "value": "Australia/Melbourne"})
    remember_fact.invoke({"key": "preferred_units", "value": "metric"})
    remember_fact.invoke({"key": "primary_vehicle", "value": "Camry"})

    filtered = recall_facts.invoke({"pattern": "prefer"})
    assert filtered["count"] == 1
    assert "preferred_units" in filtered["facts"]


def test_recall_knowledge_searches_all_agents_by_default() -> None:
    _FakeSemanticMemory("maintenance").store("Water lemon trees every 7 days in summer.")
    _FakeSemanticMemory("insights").store("Home inventory checklist item 42: check smoke alarms yearly.")

    from tools.langchain_tools import recall_knowledge

    result = recall_knowledge.invoke({"query": "lemon", "top_k": 3})
    assert len(result["hits"]) >= 1
    top = result["hits"][0]
    assert "lemon" in top["content"].lower()
    assert top["source_agent"] == "maintenance"


def test_recall_knowledge_respects_agent_scope() -> None:
    _FakeSemanticMemory("maintenance").store("Prune roses in late winter.")
    _FakeSemanticMemory("insights").store("Prune investments in cost line X.")

    from tools.langchain_tools import recall_knowledge

    result = recall_knowledge.invoke({"query": "prune", "agent_scope": "maintenance", "top_k": 5})
    assert all(h["source_agent"] == "maintenance" for h in result["hits"])


def test_voyage_fallback_to_stub_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """No VOYAGE_API_KEY → _embed() must return a valid 512-dim stub vector."""
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    from core.memory.semantic import _embed

    v = _embed("hello world")
    assert isinstance(v, list)
    assert len(v) == 512
    # deterministic — same text produces same vector
    assert _embed("hello world") == v
    # cosine of a vector with itself is ~1.0
    from core.memory.semantic import _cosine_similarity
    assert 0.99 < _cosine_similarity(v, v) <= 1.0001
