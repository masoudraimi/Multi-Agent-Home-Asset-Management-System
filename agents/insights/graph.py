"""Insights specialist LangGraph subgraph.

Standard specialist shape (see agents/_specialist.py) with no HITL branch —
spend analytics, warranty alerts, and cross-asset reports are read-only.
Semantic-memory retrieval is enabled via `agent.yaml:retrieve_semantic` and
runs automatically through the shared `retrieve` node before every `llm` call.

Insights is also the only specialist with two extra tools beyond the shared
set, both running behind this graph's existing guardrail/rate-limit/audit
perimeter as ordinary tool calls, not as a replacement for it:
  - `deep_research_analysis` (agents/insights/deep_research.py) — a
    LangChain Deep Agents-powered sub-agent for multi-step, exploratory
    analysis questions.
  - `generate_shareable_report` (agents/insights/report_agent.py) — a
    PydanticAI-powered structured-output step for turning analysis notes
    into a validated, shareable report.
See each module's docstring for why they're tools rather than graph swaps.
"""

from __future__ import annotations

from typing import Any

from agents._specialist import SpecialistGraph
from agents.insights.deep_research import deep_research_analysis
from agents.insights.report_agent import generate_shareable_report
from tools.langchain_tools import TOOLS


def build_graph(checkpointer: Any = None) -> Any:
    spec = SpecialistGraph(
        agent_name="insights", tools=[*TOOLS, deep_research_analysis, generate_shareable_report],
    )
    return spec.build(checkpointer=checkpointer)


GRAPH = build_graph()
