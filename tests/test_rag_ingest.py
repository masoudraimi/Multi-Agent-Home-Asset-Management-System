"""Tests for knowledge.rag.chunker and knowledge.rag.ingest — offline, no
VOYAGE_API_KEY or DB needed (SemanticMemory.store is mocked at the class
level, same pattern as tests/test_memory_tools.py)."""

from __future__ import annotations

import pytest

from knowledge.rag.chunker import chunk_text


def test_chunk_text_empty_returns_empty_list() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_short_text_single_chunk() -> None:
    chunks = chunk_text("Water lemon trees every 7 days in summer.")
    assert len(chunks) == 1
    assert chunks[0] == "Water lemon trees every 7 days in summer."


def test_chunk_text_long_text_splits_with_overlap() -> None:
    sentence = "Check the filter and clean any debris from the spray arm. "
    long_text = sentence * 60
    chunks = chunk_text(long_text)
    assert len(chunks) > 1
    # Sentence-aware: no chunk should end mid-word (splitter respects sentence boundaries).
    for c in chunks:
        assert c.strip().endswith(".")


def test_ingest_document_stores_one_chunk_per_piece(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: list[tuple[str, dict]] = []

    class _FakeSemanticMemory:
        def __init__(self, agent_name: str) -> None:
            self.agent_name = agent_name

        def store(self, content: str, metadata=None) -> int:
            stored.append((content, metadata or {}))
            return len(stored)

    monkeypatch.setattr("knowledge.rag.ingest.SemanticMemory", _FakeSemanticMemory)
    monkeypatch.setattr(
        "knowledge.rag.ingest.chunk_text",
        lambda text: ["chunk one.", "chunk two."],
    )

    from knowledge.rag.ingest import ingest_document

    count = ingest_document(agent_name="maintenance", source_name="test_manual", text="irrelevant, mocked")
    assert count == 2
    assert len(stored) == 2
    assert stored[0][1]["source"] == "test_manual"
    assert stored[0][1]["source_type"] == "manual"
    assert stored[0][1]["chunk_index"] == 0
    assert stored[1][1]["chunk_index"] == 1
    assert stored[0][1]["chunk_count"] == 2


def test_ingest_document_empty_text_stores_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class _FakeSemanticMemory:
        def __init__(self, agent_name: str) -> None:
            pass

        def store(self, content: str, metadata=None) -> int:
            calls.append(content)
            return 1

    monkeypatch.setattr("knowledge.rag.ingest.SemanticMemory", _FakeSemanticMemory)

    from knowledge.rag.ingest import ingest_document

    count = ingest_document(agent_name="maintenance", source_name="empty", text="   ")
    assert count == 0
    assert calls == []
