"""ConversationContext: lightweight session state.

The claude-agent-sdk manages the LLM's context window internally.
This class only tracks: working memory (asset IDs) and turn metrics for the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationContext:
    _asset_ids: dict[str, int] = field(default_factory=dict)  # name.lower() → id
    _turns: list[tuple[str, str]] = field(default_factory=list)  # (user, assistant) pairs

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

    def format_prompt(self, user_message: str) -> str:
        """Build the prompt string for the SDK.

        For the first turn, just return the message.
        For subsequent turns, include recent history as context prefix since
        the SDK starts a fresh session each time (stateless mode).
        """
        if not self._turns:
            return user_message

        # Include up to last 5 turns as context
        recent = self._turns[-5:]
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
