"""PydanticAI-powered structured report generation for the insights specialist.

Demonstrates real PydanticAI usage (github.com/pydantic/pydantic-ai) — a
small, contained structured-extraction step distinct from LangChain's own
`.with_structured_output()`, using the framework purpose-built for typed,
validated agent output: a malformed model response is retried/raised by
PydanticAI itself rather than silently passed through as loose text.

Runs as a callable @tool alongside the main LangGraph turn
(agents/insights/graph.py), not as a replacement for it — same "behind the
existing security perimeter" design as agents/insights/deep_research.py:
guardrail_in already scanned the user's message, and guardrail_tool_output
scans this tool's result like any other before it reaches the LLM or user.

Scoping note: this always talks to Anthropic directly (needs
ANTHROPIC_API_KEY), independent of the app's LLM_PROVIDER switch — a
deliberate, narrow choice for demonstrating the framework rather than
threading it through core.llm's provider abstraction.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from core.logging import get_logger
from core.metrics import emit_tool_call
from core.models import SONNET

log = get_logger(__name__)


class HomeInsightsReport(BaseModel):
    """Validated shape for a shareable home-insights report."""

    summary: str = Field(description="One-paragraph executive summary of the home's asset/maintenance state.")
    top_recommendations: list[str] = Field(
        default_factory=list, description="Up to 5 prioritized, concrete action items."
    )
    risk_items: list[str] = Field(
        default_factory=list, description="Warranty expirations, overdue maintenance, or other risks."
    )
    estimated_cost_usd: float | None = Field(
        default=None, description="Estimated near-term cost if recommendations are actioned, or null if not estimable."
    )


_report_agent: Any = None


def _get_report_agent() -> Any:
    """Built lazily — Agent(...) construction raises immediately if
    ANTHROPIC_API_KEY is unset, so importing this module must not trigger it."""
    global _report_agent
    if _report_agent is None:
        _report_agent = Agent(
            f"anthropic:{SONNET}",
            output_type=HomeInsightsReport,
            system_prompt=(
                "You turn raw home-asset analysis notes into a structured report. "
                "Be concise and concrete; never invent numbers that aren't in the notes."
            ),
        )
    return _report_agent


@tool("generate_shareable_report")
def generate_shareable_report(notes: str) -> dict:
    """Turn analysis notes you've already gathered (spend data, warranty
    status, maintenance history, etc.) into a structured, shareable report
    with a summary, prioritized recommendations, risk items, and an
    estimated cost — call this after you've done the underlying lookups,
    when the user wants something reportable rather than a chat answer.

    notes: your findings in plain text — the more concrete detail here
    (numbers, dates, asset names), the better the structured report.
    """
    log.info("report_generation_started", notes_len=len(notes))
    try:
        agent = _get_report_agent()
        result = agent.run_sync(notes)
    except Exception:
        emit_tool_call("generate_shareable_report", "error")
        log.exception("report_generation_failed")
        raise
    emit_tool_call("generate_shareable_report", "success")
    return result.output.model_dump()
