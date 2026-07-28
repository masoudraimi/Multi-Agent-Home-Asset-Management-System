"""Functional orchestration: classify → dispatch → merge.

Replaces `OrchestratorAgent._dispatch_async` with a plain async function that:
  1. Classifies the user's intent to one or more specialists.
  2. Runs single-route queries directly; fans out compound queries in parallel.
  3. Merges specialist outputs.
  4. Wraps the whole turn in a LangSmith trace so the entire flow — classifier
     + every specialist + every tool call — sits under one root span.

Interrupts (from asset's delete-approval flow) propagate through unchanged:
the specialist adapter emits a `pending_approval` UI event which `dispatch_turn`
surfaces to the caller, who resumes via `resume_graph_turn`.

Compound-query behaviour matches the legacy merge: outputs are concatenated
under **Agent Name:** headers.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langsmith import traceable

from agents.orchestrator.workflows.routing import classify_intent
from core.guardrails import Guardrails
from core.logging import bind_correlation, get_logger
from core.memory.short_term import ConversationContext
from core.registry import AgentRegistry

log = get_logger(__name__)


async def dispatch_turn(
    user_message: str,
    context: ConversationContext,
    *,
    thread_id: str | None = None,
    request_id: str | None = None,
) -> list[dict]:
    """Classify + dispatch + merge for one user turn.

    Returns the same event dict list shape that `run_turn_in_loop` used to:
        {type: "routing", agents: [...]}
        {type: "tool_call" | "tool_result" | ...}
        {type: "assistant_text", content: str}
        {type: "pending_approval", ...}    (asset interrupt only)
        {type: "metrics", ...}
    """
    orchestrator_cfg = AgentRegistry().get("orchestrator")
    guardrails = Guardrails(orchestrator_cfg.guardrails)
    if guardrails.is_injected(user_message):
        return [{"type": "assistant_text", "content": "I cannot process that request."}]

    bind_correlation(request_id=request_id, agent="orchestrator")
    return await _dispatch_traced(user_message, context, thread_id=thread_id, request_id=request_id)


@traceable(name="orchestrator_dispatch", run_type="chain")
async def _dispatch_traced(
    user_message: str,
    context: ConversationContext,
    *,
    thread_id: str | None,
    request_id: str | None,
) -> list[dict]:
    from agents.orchestrator.agent import _run_specialist_events  # avoid circular import

    routes = classify_intent(user_message)
    log.info("dispatch_classified", route=routes, request_id=request_id)
    events: list[dict] = [{"type": "routing", "agents": routes}]

    if len(routes) == 1:
        specialist_events = await _run_specialist_events(
            routes[0], user_message, context, thread_id=thread_id
        )
        events.extend(specialist_events)
        return events

    # Compound query — fan out in parallel, merge.
    tasks = [
        asyncio.create_task(
            _run_specialist_events(route, user_message, None, thread_id=thread_id)
        )
        for route in routes
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    events.extend(_merge_compound(routes, results))
    return events


def _merge_compound(routes: list[str], results: list[Any]) -> list[dict]:
    """Assemble a single UI response from N parallel specialist event streams."""
    parts: list[str] = []
    total_tokens = 0
    total_latency = 0
    total_tools = 0

    for route, result in zip(routes, results):
        if isinstance(result, BaseException):
            log.warning("dispatch_specialist_error", agent=route, error=str(result)[:200])
            continue
        text = next((e["content"] for e in result if e.get("type") == "assistant_text"), "")
        if text:
            parts.append(f"**{route.capitalize()}:**\n{text}")
        metrics = next((e for e in result if e.get("type") == "metrics"), {})
        total_tokens += int(metrics.get("tokens", 0))
        total_latency = max(total_latency, int(metrics.get("latency_ms", 0)))
        total_tools += int(metrics.get("tool_call_count", 0))

    merged_text = "\n\n".join(parts) if parts else "I was unable to gather the information."
    return [
        {"type": "assistant_text", "content": merged_text, "agents_used": list(routes)},
        {
            "type": "metrics",
            "latency_ms": total_latency,
            "tokens": total_tokens,
            "tool_call_count": total_tools,
            "agent": "orchestrator",
        },
    ]
