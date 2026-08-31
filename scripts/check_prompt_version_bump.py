"""CI check: if a specialist's system.md changed in this PR, its front-matter
`version:` must have been bumped too — otherwise prompt changes can land
silently with no traceable version bump (see agents/_specialist.py's prompt
front-matter parsing, and each agents/*/prompts/system.md's changelog).

This doesn't run/gate the LLM eval itself (that stays a separate, real-API,
manual/nightly workflow — see .github/workflows/eval-nightly.yml) — it just
emits a clearly-named GitHub Actions notice naming which prompt(s) changed,
as the attach point for a future "trigger eval on prompt change" step.

Run with:
  uv run python scripts/check_prompt_version_bump.py [base_ref] [head_ref]
  (defaults: base_ref=origin/main, head_ref=HEAD)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents._specialist import _split_front_matter

REPO_ROOT = Path(__file__).parent.parent


def _changed_prompt_files(base_ref: str, head_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}", "--", "agents/*/prompts/system.md"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _version_at(ref: str, path: str) -> int | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return None  # file didn't exist at that ref (new file)
    meta, _ = _split_front_matter(result.stdout)
    try:
        return int(meta.get("version", 0))
    except (TypeError, ValueError):
        return None


def main() -> None:
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    head_ref = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

    changed = _changed_prompt_files(base_ref, head_ref)
    if not changed:
        print("No agents/*/prompts/system.md changes in this diff.")
        return

    failures: list[str] = []
    for path in changed:
        base_version = _version_at(base_ref, path)
        head_version = _version_at(head_ref, path)
        print(f"::notice::Prompt {path} changed — base version={base_version}, head version={head_version}")
        if base_version is None:
            continue  # new prompt file; nothing to compare against
        if head_version is None or head_version <= base_version:
            failures.append(path)

    if failures:
        for path in failures:
            print(f"::error file={path}::version front-matter was not bumped for this change.")
        sys.exit(1)

    print("All changed prompts have a bumped version.")


if __name__ == "__main__":
    main()
