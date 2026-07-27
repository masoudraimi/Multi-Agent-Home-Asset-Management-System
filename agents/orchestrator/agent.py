"""OrchestratorAgent: routes user intent to specialist agents.

For single-agent queries: streams directly from the specialist.
For compound queries (e.g. "full home report"): runs specialists in parallel
and merges their responses.

Feature flag `USE_LANGGRAPH` selects between the legacy BaseAgent path and
the Phase 1 LangGraph subgraphs on a per-specialist basis:

    USE_LANGGRAPH=off      (default) — all specialists use BaseAgent
    USE_LANGGRAPH=asset               — asset uses LangGraph, others BaseAgent
    USE_LANGGRAPH=all                 — every ported specialist uses LangGraph

Phase 4 removes this flag by folding the orchestrator itself into a graph.
"""

from __future__ import annotations

import asyncio
import importlib
import os
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

# Specialists currently reachable via LangGraph. Add to this set as each phase
# ports a new specialist. Phase 1 = asset only.
_LANGGRAPH_READY = {"asset"}


def _use_langgraph(agent_name: str) -> bool:
    flag = os.environ.get("USE_LANGGRAPH", "off").lower()
    if flag == "off":
        return False
    if flag == "all":
        return agent_name in _LANGGRAPH_READY
    # Comma-separated list, e.g. "asset,maintenance"
    selected = {p.strip() for p in flag.split(",") if p.strip()}
    return agent_name in selected and agent_name in _LANGGRAPH_READY


def _load_specialist(name: str):
    module_path, class_name = _SPECIALIST_MAP[name]
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)()


async def _run_specialist_events(
    agent_name: str,
    user_message: str,
    context: ConversationContext | None,
    *,
    thread_id: str | None = None,
) -> list[dict]:
    """Dispatch to either the LangGraph adapter or the legacy BaseAgent path."""
    if _use_langgraph(agent_name):
        from agent.langgraph_adapter import run_graph_turn
        if agent_name == "asset":
            from agents.asset.graph import GRAPH
        else:
            raise NotImplementedError(f"USE_LANGGRAPH selected {agent_name} but no graph is compiled")
        return await run_graph_turn(
            GRAPH,
            user_message,
            context or ConversationContext(),
            agent_name=agent_name,
            thread_id=thread_id,
        )
    agent = _load_specialist(agent_name)
    events: list[dict] = []
    async for event in agent.run_turn_async(user_message, context):
        events.append(event)
    return events


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
        *,
        thread_id: str | None = None,
    ) -> None:
        routes = classify_intent(user_message)
        events.append({"type": "routing", "agents": routes})

        if len(routes) == 1:
            specialist_events = await _run_specialist_events(
                routes[0], user_message, context, thread_id=thread_id
            )
            events.extend(specialist_events)
        else:
            tasks = [
                asyncio.create_task(self._collect_response(route, user_message, thread_id=thread_id))
                for route in routes
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            events.extend(self._merge_responses(routes, results))

    async def _collect_response(
        self, agent_name: str, user_message: str, *, thread_id: str | None = None,
    ) -> dict:
        agent_events = await _run_specialist_events(
            agent_name, user_message, None, thread_id=thread_id
        )
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
