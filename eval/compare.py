"""Diff a freshly generated eval/results.json against the last committed
version, giving a real regression baseline over time (previously
eval/results.json was gitignored and never had a baseline to diff against).

Run after eval/run_eval.py, before the new results.json is committed:
  uv run python eval/run_eval.py
  uv run python eval/compare.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_PATH = Path(__file__).parent / "results.json"


def _load_previous() -> dict | None:
    try:
        raw = subprocess.run(
            ["git", "show", "HEAD:eval/results.json"],
            capture_output=True, text=True, check=True, cwd=Path(__file__).parent.parent,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _by_id(results: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in results}


def main() -> None:
    if not RESULTS_PATH.exists():
        print("No eval/results.json found — run eval/run_eval.py first.")
        sys.exit(1)
    current = json.loads(RESULTS_PATH.read_text())

    previous = _load_previous()
    if previous is None:
        print("No previous committed eval/results.json to compare against (first run, or not in a git repo).")
        print("This run establishes the baseline.")
        return

    print("--- Per-tier accuracy ---")
    prev_summary = previous.get("summary", {})
    curr_summary = current.get("summary", {})
    for tier in sorted(set(prev_summary) | set(curr_summary)):
        prev_acc = prev_summary.get(tier, {}).get("accuracy")
        curr_acc = curr_summary.get(tier, {}).get("accuracy")
        marker = ""
        if prev_acc is not None and curr_acc is not None and curr_acc != prev_acc:
            marker = "  <- CHANGED"
        print(f"  {tier:10s}: {prev_acc} -> {curr_acc}{marker}")

    print("\n--- Per-scenario pass/fail flips ---")
    prev_results = _by_id(previous.get("results", []))
    curr_results = _by_id(current.get("results", []))
    flips = 0
    for scenario_id in sorted(set(prev_results) | set(curr_results)):
        prev_r = prev_results.get(scenario_id)
        curr_r = curr_results.get(scenario_id)
        if prev_r is None:
            print(f"  {scenario_id}: NEW scenario (passed={curr_r['passed']})")
            continue
        if curr_r is None:
            print(f"  {scenario_id}: REMOVED scenario (was passed={prev_r['passed']})")
            continue
        if prev_r["passed"] != curr_r["passed"]:
            flips += 1
            direction = "FIXED" if curr_r["passed"] else "REGRESSED"
            print(f"  {scenario_id}: {direction} ({prev_r['passed']} -> {curr_r['passed']})")

    if flips == 0:
        print("  (none)")
    print(f"\n{flips} scenario(s) flipped pass/fail status since the last committed baseline.")


if __name__ == "__main__":
    main()
