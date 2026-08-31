"""Tests for eval.judge's LLM-as-judge scoring — mocked, no real API calls."""

from __future__ import annotations

import pytest

from eval.judge import judge_answer


def test_judge_answer_parses_clean_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "eval.judge.simple_complete",
        lambda *a, **kw: '{"groundedness": 5, "relevance": 4, "reasoning": "Accurate and on-topic."}',
    )
    result = judge_answer("query", "answer")
    assert result["groundedness"] == 5
    assert result["relevance"] == 4
    assert result["reasoning"] == "Accurate and on-topic."


def test_judge_answer_parses_json_with_surrounding_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "eval.judge.simple_complete",
        lambda *a, **kw: 'Here is my rating:\n{"groundedness": 3, "relevance": 3, "reasoning": "ok"}\nDone.',
    )
    result = judge_answer("query", "answer")
    assert result["groundedness"] == 3


def test_judge_answer_never_raises_on_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a, **kw):
        raise RuntimeError("provider down")

    monkeypatch.setattr("eval.judge.simple_complete", _raise)
    result = judge_answer("query", "answer")
    assert result["groundedness"] is None
    assert result["relevance"] is None


def test_judge_answer_handles_unparseable_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("eval.judge.simple_complete", lambda *a, **kw: "not json at all")
    result = judge_answer("query", "answer")
    assert result["groundedness"] is None
    assert "unparseable" in result["reasoning"]
