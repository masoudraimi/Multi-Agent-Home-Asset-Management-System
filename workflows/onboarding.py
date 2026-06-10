"""Workflow: LLM-as-judge review of a partially-filled asset draft before saving."""

from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic

QUESTIONS_PATH = Path(__file__).parent.parent / "data" / "asset_questions.json"

_JUDGE_MODEL = "claude-haiku-4-5-20251001"


def get_onboarding_questions(asset_type: str) -> dict:
    """Return the type-specific question list for guided asset onboarding."""
    questions_data = json.loads(QUESTIONS_PATH.read_text())
    category = asset_type.lower().strip()

    # Fuzzy map common synonyms to canonical categories
    _synonyms = {
        "plant": "plants_trees", "tree": "plants_trees", "garden plant": "plants_trees",
        "air conditioner": "HVAC", "ac": "HVAC", "heating": "HVAC", "cooling": "HVAC",
        "car": "vehicle", "truck": "vehicle", "motorbike": "vehicle",
        "fridge": "appliances", "washing machine": "appliances", "dishwasher": "appliances",
        "tap": "plumbing", "hot water": "plumbing", "pipes": "plumbing",
        "fence": "exterior", "roof": "exterior", "deck": "exterior", "gutters": "exterior",
        "smoke alarm": "electrical", "switchboard": "electrical", "solar": "electrical",
    }
    mapped = _synonyms.get(category, category)
    questions = questions_data.get(mapped, questions_data.get("other", []))

    return {
        "asset_type": mapped,
        "questions": questions,
        "instructions": (
            "Ask these questions one at a time. After collecting the answers, "
            "call review_asset_draft to check completeness before saving."
        ),
    }


def review_asset_draft(draft_json: str) -> dict:
    """LLM-as-judge: review a partially-filled asset draft for completeness and correctness.

    draft_json: JSON string of the collected asset fields so far
    """
    try:
        draft = json.loads(draft_json)
    except json.JSONDecodeError:
        return {"confidence": "low", "missing_fields": [], "suggestions": ["Invalid JSON draft"]}

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    asset_type = draft.get("category", "unknown")

    prompt = f"""You are reviewing a home asset record before it is saved to a database.
Asset type: {asset_type}
Collected fields: {json.dumps(draft, indent=2)}

Evaluate this asset record and respond in JSON with exactly these fields:
{{
  "confidence": "high" | "medium" | "low",
  "missing_fields": ["list of important fields that are missing for this asset type"],
  "suspicious_values": ["list of values that look wrong or unlikely"],
  "suggestions": ["short actionable suggestions to improve the record"],
  "ready_to_save": true | false
}}

Be concise. For a {asset_type}, the most important fields are: name, category, and either a date or location.
Only flag genuinely important missing fields — not optional ones."""

    message = client.messages.create(
        model=_JUDGE_MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "confidence": "medium",
            "missing_fields": [],
            "suspicious_values": [],
            "suggestions": [raw[:200]],
            "ready_to_save": True,
        }

    return result
