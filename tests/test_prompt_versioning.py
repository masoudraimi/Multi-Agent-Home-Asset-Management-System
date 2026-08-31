"""Tests for agents._specialist's prompt front-matter parsing."""

from __future__ import annotations

from agents._specialist import _load_prompt_version, _load_system_prompt, _split_front_matter


def test_split_front_matter_extracts_meta_and_body():
    raw = "---\nversion: 3\nlast_updated: 2026-01-01\n---\nHello world.\n"
    meta, body = _split_front_matter(raw)
    assert meta["version"] == 3
    assert str(meta["last_updated"]) == "2026-01-01"  # YAML parses unquoted dates to datetime.date
    assert body == "Hello world.\n"


def test_split_front_matter_no_frontmatter_returns_body_unchanged():
    raw = "No front matter here.\n"
    meta, body = _split_front_matter(raw)
    assert meta == {}
    assert body == raw


def test_load_system_prompt_strips_front_matter_for_all_specialists():
    for agent in ("asset", "maintenance", "insights"):
        prompt = _load_system_prompt(agent)
        assert not prompt.startswith("---")
        assert "version:" not in prompt.splitlines()[0]


def test_load_prompt_version_returns_positive_int_for_all_specialists():
    for agent in ("asset", "maintenance", "insights"):
        assert _load_prompt_version(agent) >= 1


def test_load_prompt_version_defaults_to_zero_when_missing():
    meta, _ = _split_front_matter("no front matter")
    assert meta.get("version", 0) == 0
