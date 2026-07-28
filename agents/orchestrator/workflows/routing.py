"""Routing workflow: intent classification for orchestrator."""

from __future__ import annotations

import json

from core.logging import get_logger
from core.models import simple_complete

log = get_logger(__name__)

_VALID_AGENTS = {"asset", "maintenance", "insights"}

_ROUTING_PROMPT = """You are a home asset management router. Classify user messages and route them to the right specialist agent.

Available agents:
- asset: inventory, onboarding, adding assets, searching assets, suggestions for missing assets
- maintenance: scheduling, plant care, overdue tasks, Telegram digest, service reminders
- insights: spend analytics, warranty alerts, home health reports, cost summaries

Respond with ONLY a JSON array of agent names. Examples:
- "What appliances do I have?" -> ["asset"]
- "When should I service the HVAC?" -> ["maintenance"]
- "How much have I spent on the car?" -> ["insights"]
- "Give me a full home health report" -> ["maintenance", "insights"]

Always respond with a valid JSON array. Default to ["asset"] if unsure.

User message: {message}"""


def classify_intent(user_message: str) -> list[str]:
    """Classify user intent and return a list of agent names to route to.

    Falls back to `["asset"]` on any error (network hiccup, parse failure,
    unknown labels). The fallback is logged so operators can see when the
    classifier is silently degrading routing quality.
    """
    try:
        raw = simple_complete("haiku", 50, _ROUTING_PROMPT.format(message=user_message))
        routes = json.loads(raw)
        if isinstance(routes, list):
            valid = [r for r in routes if r in _VALID_AGENTS]
            if valid:
                return valid
            log.warning("classify_no_valid_routes", raw=raw[:120], preview=user_message[:80])
    except Exception:
        log.exception("classify_intent_failed", preview=user_message[:80])
    return ["asset"]
