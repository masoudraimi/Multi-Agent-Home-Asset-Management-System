"""Specialist dispatch — bridges orchestrator/dispatcher.py to the compiled graphs.

Post-Phase-6 the LangGraph specialists are the only runtime path — the
`USE_LANGGRAPH` flag is gone, and the old `OrchestratorAgent` class along
with it. `dispatch_turn` (in `agents/orchestrator/dispatcher.py`) is the
single entry point; this module holds the small `_run_specialist_events`
helper that maps agent_name → compiled graph.
"""

from __future__ import annotations

from core.memory.short_term import ConversationContext


async def _run_specialist_events(
    agent_name: str,
    user_message: str,
    context: ConversationContext | None,
    *,
    thread_id: str | None = None,
) -> list[dict]:
    """Route a single-specialist turn through its LangGraph subgraph."""
    from agent.langgraph_adapter import run_graph_turn

    if agent_name == "asset":
        from agents.asset.graph import GRAPH
    elif agent_name == "maintenance":
        from agents.maintenance.graph import GRAPH
    elif agent_name == "insights":
        from agents.insights.graph import GRAPH
    else:
        raise ValueError(f"Unknown specialist: {agent_name}")

    return await run_graph_turn(
        GRAPH,
        user_message,
        context or ConversationContext(),
        agent_name=agent_name,
        thread_id=thread_id,
    )
