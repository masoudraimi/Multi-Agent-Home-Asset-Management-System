"""Maintenance specialist LangGraph subgraph.

Standard specialist shape (see agents/_specialist.py) with no HITL branch —
maintenance scheduling, plant care, and reminders don't require approval
gates. Semantic-memory retrieval is enabled via `agent.yaml:retrieve_semantic`
and runs automatically through the shared `retrieve` node before every `llm`
call.
"""

from __future__ import annotations

from typing import Any

from agents._specialist import SpecialistGraph
from tools.langchain_tools import TOOLS


def build_graph(checkpointer: Any = None) -> Any:
    spec = SpecialistGraph(agent_name="maintenance", tools=TOOLS)
    return spec.build(checkpointer=checkpointer)


GRAPH = build_graph()
