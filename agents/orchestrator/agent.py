"""OrchestratorAgent: routes user intent to specialist agents.

For single-agent queries: streams directly from the specialist.
For compound queries (e.g. "full home report"): runs specialists in parallel
and merges their responses.
"""

from __future__ import annotations

import asyncio
import importlib
from typing import Generator

from core.guardrails import Guardrails
from core.memory.short_term import ConversationContext
from core.observability import get_tracer
from core.registry import AgentRegistry
from agents.orchestrator.workflows.routing import classify_intent

_SPECIALIST_MAP = {
    "asset": ("agents.asset.agent", "AssetAgent"),
    "maintenance": ("agents.maintenance.agent", "MaintenanceAgent"),
    "insights": ("agents.insights.agent", "InsightsAgent"),
}


def _load_specialist(name: str):
    module_path, class_name = _SPECIALIST_MAP[name]
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)()


class OrchestratorAgent:
    def __init__(self) -> None:
        self.config = AgentRegistry().get("orchestrator")
        self.tracer = get_tracer("orchestrator")
        self.guardrails = Guardrails(self.config.guardrails)

    def run_turn(
        self,
        user_message: str,
        context: ConversationContext | None = None,
    ) -> Generator[dict, None, None]:
        """Synchronous generator yielding UI events."""
        if context is None:
            context = ConversationContext()

        if self.guardrails.is_injected(user_message):
            yield {"type": "assistant_text", "content": "I cannot process that request."}
            return

        with self.tracer.start_as_current_span("orchestrator.run_turn") as span:
            span.set_attribute("agent_name", "orchestrator")
            events: list[dict] = []
            asyncio.run(self._dispatch_async(user_message, context, events))
            yield from events

    async def _dispatch_async(
        self,
        user_message: str,
        context: ConversationContext,
        events: list[dict],
    ) -> None:
        routes = classify_intent(user_message)
        events.append({"type": "routing", "agents": routes})

        if len(routes) == 1:
            agent = _load_specialist(routes[0])
            collected: list[dict] = []
            async for event in agent.run_turn_async(user_message, context):
                events.append(event)
        else:
            tasks = [
                asyncio.create_task(self._collect_response(route, user_message))
                for route in routes
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            events.extend(self._merge_responses(routes, results))

    async def _collect_response(
        self, agent_name: str, user_message: str
    ) -> dict:
        agent = _load_specialist(agent_name)
        agent_events: list[dict] = []
        async for event in agent.run_turn_async(user_message):
            agent_events.append(event)
        text = next(
            (e["content"] for e in agent_events if e["type"] == "assistant_text"), ""
        )
        metrics = next(
            (e for e in agent_events if e["type"] == "metrics"), {}
        )
        return {"agent": agent_name, "text": text, "events": agent_events, "metrics": metrics}

    def _merge_responses(
        self, routes: list[str], results: list[object]
    ) -> list[dict]:
        parts = []
        total_tokens = 0
        total_latency = 0
        total_tools = 0

        for result in results:
            if isinstance(result, dict):
                if result.get("text"):
                    agent_label = result["agent"].capitalize()
                    parts.append(f"**{agent_label}:**\n{result['text']}")
                m = result.get("metrics", {})
                total_tokens += m.get("tokens", 0)
                total_latency = max(total_latency, m.get("latency_ms", 0))
                total_tools += m.get("tool_call_count", 0)
                for event in result.get("events", []):
                    if event["type"] in ("tool_call", "tool_result"):
                        yield_event = {**event, "agent": result["agent"]}
                        pass

        merged_text = "\n\n".join(parts) if parts else "I was unable to gather the information."
        return [
            {"type": "assistant_text", "content": merged_text, "agents_used": routes},
            {
                "type": "metrics",
                "latency_ms": total_latency,
                "tokens": total_tokens,
                "tool_call_count": total_tools,
                "agent": "orchestrator",
            },
        ]
