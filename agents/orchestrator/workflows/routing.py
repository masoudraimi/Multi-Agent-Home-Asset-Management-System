"""Routing workflow: intent classification for orchestrator."""

from __future__ import annotations

import json

from core.models import HAIKU, anthropic_client

_ROUTE_MODEL = HAIKU
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
    """Classify user intent and return a list of agent names to route to."""
    client = anthropic_client()
    try:
        resp = client.messages.create(
            model=_ROUTE_MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": _ROUTING_PROMPT.format(message=user_message)}],
        )
        raw = resp.content[0].text.strip()
        routes = json.loads(raw)
        if isinstance(routes, list):
            valid = [r for r in routes if r in _VALID_AGENTS]
            return valid or ["asset"]
    except Exception:
        pass
    return ["asset"]
