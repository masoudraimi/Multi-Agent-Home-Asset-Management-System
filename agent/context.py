from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

_WINDOW_TURNS = 10  # full turns to keep before summarising
_SUMMARY_TOKEN_THRESHOLD = 6000  # rough char proxy (~4 chars/token)


@dataclass
class ConversationContext:
    """Manages message history with sliding-window summarisation and working memory."""

    messages: list[dict] = field(default_factory=list)
    _asset_ids_mentioned: dict[str, int] = field(default_factory=dict)  # name → id
    _summary: str | None = None

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_call(self, tool_call_id: str, name: str, arguments: str) -> None:
        # Append to the last assistant message's tool_calls list or create new
        last = self.messages[-1] if self.messages else None
        if last and last["role"] == "assistant" and isinstance(last.get("content"), list):
            last["content"].append(
                {"type": "tool_use", "id": tool_call_id, "name": name, "input": arguments}
            )
        else:
            self.messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {"name": name, "arguments": arguments},
                    }
                ],
            })

    def add_tool_result(self, tool_call_id: str, result: str) -> None:
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        })

    def track_asset(self, name: str, asset_id: int) -> None:
        self._asset_ids_mentioned[name.lower()] = asset_id

    @property
    def working_memory_hint(self) -> str:
        if not self._asset_ids_mentioned:
            return ""
        items = ", ".join(f"{n} (id={i})" for n, i in self._asset_ids_mentioned.items())
        return f"\n[Assets mentioned this session: {items}]"

    @property
    def token_estimate(self) -> int:
        total = sum(len(str(m.get("content", ""))) for m in self.messages)
        return total // 4

    def maybe_summarise(self) -> bool:
        """Summarise old messages if history is getting long. Returns True if summarised."""
        total_chars = sum(len(str(m.get("content", ""))) for m in self.messages)
        if total_chars < _SUMMARY_TOKEN_THRESHOLD:
            return False

        # Keep only the last _WINDOW_TURNS * 2 messages (each turn = user + assistant)
        keep_from = max(0, len(self.messages) - _WINDOW_TURNS * 2)
        to_summarise = self.messages[:keep_from]
        if not to_summarise:
            return False

        summary_text = _summarise_messages(to_summarise)
        self._summary = summary_text
        self.messages = [
            {"role": "system", "content": f"[Earlier conversation summary]\n{summary_text}"},
            *self.messages[keep_from:],
        ]
        return True

    def to_api_messages(self) -> list[dict]:
        return self.messages


def _summarise_messages(messages: list[dict]) -> str:
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    condensed = "\n".join(
        f"{m['role'].upper()}: {str(m.get('content', ''))[:300]}" for m in messages
    )
    resp = client.chat.completions.create(
        model="anthropic/claude-haiku-4-5",
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarise this conversation in 3-5 bullet points, "
                    "preserving key facts (asset names, IDs, dates, costs):\n\n"
                    + condensed
                ),
            }
        ],
        max_tokens=300,
    )
    return resp.choices[0].message.content or ""
