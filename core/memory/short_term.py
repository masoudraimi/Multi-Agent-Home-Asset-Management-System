"""Short-term session memory: working memory for asset IDs and recent turns.

Public interface is identical to the original agent/context.py so all
existing callers continue to work without modification — only the internal
turn-selection in `format_prompt`/`recent_turns_within_budget` changed, from
a fixed "last 5 turns" cutoff to a token-budget-aware walk.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Fraction of the active model's context window reserved for short-term
# scrollback — the rest is left for the system prompt, tool schemas, and the
# current turn. Tunable; not meant to be precise, just a reasonable default.
_HISTORY_BUDGET_FRACTION = 0.05


def _default_budget() -> int:
    from core.models import CONTEXT_WINDOW_TOKENS
    return int(CONTEXT_WINDOW_TOKENS.get("sonnet", 200_000) * _HISTORY_BUDGET_FRACTION)


@dataclass
class ConversationContext:
    _asset_ids: dict[str, int] = field(default_factory=dict)
    _turns: list[tuple[str, str]] = field(default_factory=list)

    def track_asset(self, name: str, asset_id: int) -> None:
        if name and asset_id:
            self._asset_ids[name.lower()] = asset_id

    def add_turn(self, user: str, assistant: str) -> None:
        self._turns.append((user, assistant))

    @property
    def working_memory_hint(self) -> str:
        if not self._asset_ids:
            return ""
        items = ", ".join(f"{n} (id={i})" for n, i in list(self._asset_ids.items())[-8:])
        return f"\n\n[Assets referenced this session: {items}]"

    def recent_turns_within_budget(self, max_context_tokens: int | None = None) -> list[tuple[str, str]]:
        """Walk turns newest-to-oldest, greedily including whole turns while
        under `max_context_tokens` (defaults to a per-model history budget).
        Token-aware rather than turn-count-aware: a handful of very long
        turns can use the whole budget, while many short turns can exceed
        five without being cut."""
        budget = max_context_tokens if max_context_tokens is not None else _default_budget()
        selected: list[tuple[str, str]] = []
        used = 0
        for u, a in reversed(self._turns):
            cost = (len(u) + len(a)) // 4  # same heuristic as token_estimate
            if used + cost > budget and selected:
                break
            selected.append((u, a))
            used += cost
        return list(reversed(selected))

    def format_prompt(self, user_message: str, *, max_context_tokens: int | None = None) -> str:
        if not self._turns:
            return user_message
        recent = self.recent_turns_within_budget(max_context_tokens)
        history_lines = []
        for u, a in recent:
            history_lines.append(f"User: {u}")
            history_lines.append(f"Assistant: {a}")
        history = "\n".join(history_lines)
        return f"[Previous conversation]\n{history}\n\n[Current message]\n{user_message}"

    @property
    def token_estimate(self) -> int:
        total = sum(len(u) + len(a) for u, a in self._turns)
        return total // 4
