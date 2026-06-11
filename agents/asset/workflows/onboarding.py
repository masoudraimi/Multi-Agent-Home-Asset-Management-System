"""Asset onboarding workflow: LLM-as-judge review with HumanApprovalRequested event."""

from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic

from core.event_bus import EventBus
from core.events import HumanApprovalRequested

QUESTIONS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "asset_questions.json"

_JUDGE_MODEL = "claude-haiku-4-5-20251001"

_SYNONYMS = {
    "plant": "plants_trees", "tree": "plants_trees", "garden plant": "plants_trees",
    "air conditioner": "HVAC", "ac": "HVAC", "heating": "HVAC", "cooling": "HVAC",
    "car": "vehicle", "truck": "vehicle", "motorbike": "vehicle",
    "fridge": "appliances", "washing machine": "appliances", "dishwasher": "appliances",
    "tap": "plumbing", "hot water": "plumbing", "pipes": "plumbing",
    "fence": "exterior", "roof": "exterior", "deck": "exterior", "gutters": "exterior",
    "smoke alarm": "electrical", "switchboard": "electrical", "solar": "electrical",
}


def get_onboarding_questions(asset_type: str) -> dict:
    """Return type-specific guided questions for asset onboarding."""
    questions_data = json.loads(QUESTIONS_PATH.read_text())
    category = asset_type.lower().strip()
    mapped = _SYNONYMS.get(category, category)
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
    """LLM-as-judge: review a partially-filled asset draft for completeness.

    If ready_to_save is true, also publishes a HumanApprovalRequested event
    so the Streamlit UI can render a confirmation card.
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
Only flag genuinely important missing fields, not optional ones."""

    message = client.messages.create(
        model=_JUDGE_MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
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

    if result.get("ready_to_save"):
        EventBus().publish(HumanApprovalRequested(
            request_id=draft.get("name", "asset")[:8],
            agent_name="asset",
            action_description=f"Save asset: {draft.get('name', 'unnamed')} ({asset_type})",
            payload=draft,
        ))

    return result
