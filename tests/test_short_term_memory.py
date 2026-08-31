"""Tests for core.memory.short_term's token-budget-aware turn selection —
proves it's token-aware, not turn-count-aware (the old fixed "last 5" cutoff)."""

from __future__ import annotations

from core.memory.short_term import ConversationContext


def test_many_short_turns_under_budget_all_included():
    ctx = ConversationContext()
    for i in range(8):
        ctx.add_turn(f"q{i}", f"a{i}")
    # 8 short turns comfortably fit a generous budget — old behavior capped at 5.
    recent = ctx.recent_turns_within_budget(max_context_tokens=10_000)
    assert len(recent) == 8
    assert recent[0] == ("q0", "a0")
    assert recent[-1] == ("q7", "a7")


def test_long_turns_are_dropped_even_under_five_total():
    ctx = ConversationContext()
    long_text = "x" * 4000  # ~1000 tokens each turn (len//4)
    for i in range(3):
        ctx.add_turn(long_text, long_text)
    recent = ctx.recent_turns_within_budget(max_context_tokens=1000)
    # Budget only fits ~1 of these turns even though there are just 3 total.
    assert len(recent) < 3
    assert len(recent) >= 1


def test_at_least_one_turn_always_included_even_over_budget():
    ctx = ConversationContext()
    ctx.add_turn("x" * 10_000, "y" * 10_000)
    recent = ctx.recent_turns_within_budget(max_context_tokens=1)
    assert len(recent) == 1  # never returns zero turns just because the newest exceeds budget


def test_order_is_preserved_oldest_to_newest():
    ctx = ConversationContext()
    for i in range(4):
        ctx.add_turn(f"q{i}", f"a{i}")
    recent = ctx.recent_turns_within_budget(max_context_tokens=10_000)
    assert recent == [("q0", "a0"), ("q1", "a1"), ("q2", "a2"), ("q3", "a3")]


def test_format_prompt_uses_budget_aware_selection():
    ctx = ConversationContext()
    for i in range(8):
        ctx.add_turn(f"q{i}", f"a{i}")
    prompt = ctx.format_prompt("current question", max_context_tokens=10_000)
    assert "q0" in prompt  # oldest turn retained since budget is generous
    assert "current question" in prompt


def test_format_prompt_default_budget_does_not_crash():
    ctx = ConversationContext()
    ctx.add_turn("hello", "hi there")
    prompt = ctx.format_prompt("what's up")
    assert "what's up" in prompt


def test_token_estimate_and_working_memory_hint_unaffected():
    ctx = ConversationContext()
    ctx.add_turn("abcd", "efgh")  # 8 chars -> 2 tokens
    assert ctx.token_estimate == 2
    ctx.track_asset("Fridge", 5)
    assert "fridge (id=5)" in ctx.working_memory_hint


def test_empty_context_returns_empty_selection():
    ctx = ConversationContext()
    assert ctx.recent_turns_within_budget() == []
    assert ctx.format_prompt("hi") == "hi"
