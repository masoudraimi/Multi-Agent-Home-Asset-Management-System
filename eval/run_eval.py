"""Run the benchmark suite and write results to eval/results.json.

Requires real credentials — VOYAGE_API_KEY, ANTHROPIC_API_KEY (or
OPENROUTER_API_KEY), and a live DATABASE_URL with seeded data matching
scenarios.json's expectations. This is an integration eval that hits the
real LLM/DB stack by design; do not run it on every PR — see
.github/workflows/eval-nightly.yml for the manual/nightly trigger that
keeps this cost off every push.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from agent.runner import run_turn
from core.memory.short_term import ConversationContext
from eval.judge import judge_answer

SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"
RESULTS_PATH = Path(__file__).parent / "results.json"
HISTORY_DIR = Path(__file__).parent / "history"


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

    # Mechanical scoring (unchanged) — this is the pass/fail gate.
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

    # LLM-as-judge — additive signal, never gates `passed` (a flaky judge
    # call shouldn't silently fail an otherwise-correct scenario).
    judge = judge_answer(scenario["query"], final_answer)

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
        "judge_groundedness": judge.get("groundedness"),
        "judge_relevance": judge.get("relevance"),
        "judge_reasoning": judge.get("reasoning"),
    }


def _mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def main() -> None:
    scenarios = json.loads(SCENARIOS_PATH.read_text())
    results = []
    tiers = sorted({s["tier"] for s in scenarios})
    tier_stats: dict[str, dict] = {
        tier: {"total": 0, "passed": 0, "latency": [], "tokens": [], "groundedness": [], "relevance": []}
        for tier in tiers
    }

    for i, scenario in enumerate(scenarios, 1):
        print(f"[{i}/{len(scenarios)}] {scenario['tier']:8s} | {scenario['query'][:60]}...")
        result = run_scenario(scenario)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"           {status} | tools={result['tool_call_count']} | {result['latency_ms']}ms | "
            f"{result['tokens']} tokens | groundedness={result['judge_groundedness']} "
            f"relevance={result['judge_relevance']}"
        )

        t = tier_stats[result["tier"]]
        t["total"] += 1
        if result["passed"]:
            t["passed"] += 1
        t["latency"].append(result["latency_ms"])
        t["tokens"].append(result["tokens"])
        t["groundedness"].append(result["judge_groundedness"])
        t["relevance"].append(result["judge_relevance"])

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
            "avg_judge_groundedness": _mean(stats["groundedness"]),
            "avg_judge_relevance": _mean(stats["relevance"]),
        }

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary,
        "results": results,
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2) + "\n")

    HISTORY_DIR.mkdir(exist_ok=True)
    snapshot_path = HISTORY_DIR / f"results-{datetime.now(timezone.utc):%Y-%m-%d}.json"
    snapshot_path.write_text(json.dumps(output, indent=2) + "\n")

    print("\n--- Summary ---")
    for tier, s in summary.items():
        print(
            f"{tier:8s}: {s['passed']}/{s['total']} ({s['accuracy']*100:.0f}%) | "
            f"avg {s['avg_latency_ms']}ms | avg {s['avg_tokens']} tokens | "
            f"groundedness={s['avg_judge_groundedness']} relevance={s['avg_judge_relevance']}"
        )
    print(f"\nResults saved to {RESULTS_PATH} (snapshot: {snapshot_path})")


if __name__ == "__main__":
    main()
