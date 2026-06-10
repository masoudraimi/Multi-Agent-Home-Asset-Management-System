"""Run the 15-scenario benchmark suite and write results to eval/results.json."""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from agent.context import ConversationContext
from agent.runner import run_turn

SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"
RESULTS_PATH = Path(__file__).parent / "results.json"


def run_scenario(scenario: dict) -> dict:
    ctx = ConversationContext()
    tool_calls_made: list[str] = []
    final_answer = ""
    latency_ms = 0
    tokens = 0

    for event in run_turn(scenario["query"], ctx):
        if event["type"] == "tool_call":
            tool_calls_made.append(event["name"])
        elif event["type"] == "assistant_text":
            final_answer = event["content"]
        elif event["type"] == "metrics":
            latency_ms = event["latency_ms"]
            tokens = event["tokens"]

    # Score
    expected_tools = set(scenario["expected_tools"])
    used_tools = set(tool_calls_made)
    tool_hit = expected_tools.issubset(used_tools)

    answer_lower = final_answer.lower()
    keyword_hits = [
        kw for kw in scenario["expected_answer_contains"]
        if kw.lower() in answer_lower
    ]
    keyword_score = (
        len(keyword_hits) / len(scenario["expected_answer_contains"])
        if scenario["expected_answer_contains"]
        else 1.0
    )

    passed = tool_hit and keyword_score >= 0.75

    return {
        "id": scenario["id"],
        "tier": scenario["tier"],
        "query": scenario["query"],
        "passed": passed,
        "tool_hit": tool_hit,
        "keyword_score": round(keyword_score, 2),
        "expected_tools": list(expected_tools),
        "tools_used": tool_calls_made,
        "tool_call_count": len(tool_calls_made),
        "latency_ms": latency_ms,
        "tokens": tokens,
        "answer_preview": final_answer[:200],
    }


def main() -> None:
    scenarios = json.loads(SCENARIOS_PATH.read_text())
    results = []
    tier_stats: dict[str, dict] = {
        "simple": {"total": 0, "passed": 0, "latency": [], "tokens": []},
        "moderate": {"total": 0, "passed": 0, "latency": [], "tokens": []},
        "complex": {"total": 0, "passed": 0, "latency": [], "tokens": []},
    }

    for i, scenario in enumerate(scenarios, 1):
        print(f"[{i}/{len(scenarios)}] {scenario['tier']:8s} | {scenario['query'][:60]}...")
        result = run_scenario(scenario)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"           {status} | tools={result['tool_call_count']} | {result['latency_ms']}ms | {result['tokens']} tokens")

        t = tier_stats[result["tier"]]
        t["total"] += 1
        if result["passed"]:
            t["passed"] += 1
        t["latency"].append(result["latency_ms"])
        t["tokens"].append(result["tokens"])

    summary = {}
    for tier, stats in tier_stats.items():
        if stats["total"] == 0:
            continue
        summary[tier] = {
            "accuracy": round(stats["passed"] / stats["total"], 2),
            "passed": stats["passed"],
            "total": stats["total"],
            "avg_latency_ms": int(sum(stats["latency"]) / len(stats["latency"])),
            "avg_tokens": int(sum(stats["tokens"]) / len(stats["tokens"])),
        }

    output = {"summary": summary, "results": results}
    RESULTS_PATH.write_text(json.dumps(output, indent=2))

    print("\n--- Summary ---")
    for tier, s in summary.items():
        print(f"{tier:8s}: {s['passed']}/{s['total']} ({s['accuracy']*100:.0f}%) | "
              f"avg {s['avg_latency_ms']}ms | avg {s['avg_tokens']} tokens")
    print(f"\nResults saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
