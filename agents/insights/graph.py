"""Insights specialist LangGraph subgraph.

Standard specialist shape (see agents/_specialist.py) with no HITL branch —
spend analytics, warranty alerts, and cross-asset reports are read-only.
Semantic-memory retrieval is declared in `agent.yaml:retrieve_semantic`
and will be wired in Phase 5.

Feature-flagged via `USE_LANGGRAPH=insights` (or `all`).
"""

from __future__ import annotations

from typing import Any

from agents._specialist import SpecialistGraph
from tools.langchain_tools import TOOLS


def build_graph(checkpointer: Any = None) -> Any:
    spec = SpecialistGraph(agent_name="insights", tools=TOOLS)
    return spec.build(checkpointer=checkpointer)


GRAPH = build_graph()
