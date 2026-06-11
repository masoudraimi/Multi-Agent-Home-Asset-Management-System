"""EvalFramework: structured evaluation harness for all agents.

Supports per-agent scenarios, cost tracking, and cross-agent comparison.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvalResult:
    scenario_id: str
    agent_name: str
    query: str
    tool_accuracy: float
    keyword_coverage: float
    latency_ms: int
    cost_usd: float
    guardrail_triggered: bool
    human_approval_required: bool
    passed: bool
    tools_used: list[str] = field(default_factory=list)
    answer_preview: str = ""


class EvalFramework:
    COST_INPUT_PER_1K = 0.003
    COST_OUTPUT_PER_1K = 0.015

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._results: list[EvalResult] = []

    def run_scenario(self, scenario: dict, agent: Any) -> EvalResult:
        """Run a single scenario against an agent instance."""
        import asyncio

        events: list[dict] = []

        async def collect() -> None:
            async for event in agent.run_turn_async(scenario["query"]):
                events.append(event)

        start = time.monotonic()
        asyncio.run(collect())
        latency_ms = int((time.monotonic() - start) * 1000)

        tools_used = [e["name"] for e in events if e.get("type") == "tool_call"]
        answer = next((e["content"] for e in events if e.get("type") == "assistant_text"), "")
        metrics_event = next((e for e in events if e.get("type") == "metrics"), {})
        total_tokens = metrics_event.get("tokens", 0)
        guardrail_hit = any(e.get("guardrail_triggered") for e in events)
        approval_needed = any(e.get("type") == "human_approval_requested" for e in events)

        expected_tools = set(scenario.get("expected_tools", []))
        used_set = set(tools_used)
        tool_accuracy = (
            len(expected_tools & used_set) / len(expected_tools) if expected_tools else 1.0
        )

        keywords = scenario.get("expected_answer_contains", [])
        kw_hits = [kw for kw in keywords if kw.lower() in answer.lower()]
        keyword_coverage = len(kw_hits) / len(keywords) if keywords else 1.0

        cost_usd = (total_tokens * self.COST_INPUT_PER_1K) / 1000

        result = EvalResult(
            scenario_id=scenario["id"],
            agent_name=self.agent_name,
            query=scenario["query"],
            tool_accuracy=round(tool_accuracy, 2),
            keyword_coverage=round(keyword_coverage, 2),
            latency_ms=latency_ms,
            cost_usd=round(cost_usd, 5),
            guardrail_triggered=guardrail_hit,
            human_approval_required=approval_needed,
            passed=tool_accuracy >= 1.0 and keyword_coverage >= 0.75,
            tools_used=tools_used,
            answer_preview=answer[:200],
        )
        self._results.append(result)
        return result

    def compare_agents(self, scenario: dict, agents: dict[str, Any]) -> dict[str, EvalResult]:
        """Run the same scenario against multiple agents."""
        return {
            name: EvalFramework(name).run_scenario(scenario, agent)
            for name, agent in agents.items()
        }

    def summary(self) -> dict:
        if not self._results:
            return {}
        passed = sum(1 for r in self._results if r.passed)
        return {
            "total": len(self._results),
            "passed": passed,
            "accuracy": round(passed / len(self._results), 2),
            "avg_latency_ms": int(
                sum(r.latency_ms for r in self._results) / len(self._results)
            ),
            "total_cost_usd": round(sum(r.cost_usd for r in self._results), 4),
            "guardrail_triggered_count": sum(1 for r in self._results if r.guardrail_triggered),
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({
            "agent": self.agent_name,
            "summary": self.summary(),
            "results": [asdict(r) for r in self._results],
        }, indent=2))


def load_benchmarks(agent_name: str) -> list[dict]:
    """Load benchmark scenarios for a specific agent."""
    bench_path = Path(__file__).parent / "benchmarks" / f"{agent_name}.json"
    if not bench_path.exists():
        return []
    return json.loads(bench_path.read_text())
