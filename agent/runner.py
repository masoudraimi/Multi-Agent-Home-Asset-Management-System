from __future__ import annotations

import json
import os
import time
from typing import Generator

from openai import OpenAI

from agent.context import ConversationContext
from agent.system_prompt import get_system_prompt
from tools import TOOL_DISPATCH, TOOL_SCHEMAS


def get_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )


MODEL = "anthropic/claude-sonnet-4-6"


def run_turn(
    user_message: str,
    context: ConversationContext,
) -> Generator[dict, None, None]:
    """Run one conversation turn. Yields events for the UI to render.

    Event types:
      {"type": "tool_call", "name": str, "args": dict, "call_id": str}
      {"type": "tool_result", "name": str, "call_id": str, "result": dict}
      {"type": "assistant_text", "content": str}
      {"type": "metrics", "latency_ms": int, "tokens": int, "tool_call_count": int}
    """
    client = get_client()
    context.add_user(user_message + context.working_memory_hint)
    context.maybe_summarise()

    system = get_system_prompt()
    tool_call_count = 0
    start = time.monotonic()

    messages = [{"role": "system", "content": system}] + context.to_api_messages()

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        msg = choice.message

        # Accumulate assistant message into the rolling messages list
        messages.append(msg.model_dump(exclude_none=True))

        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                yield {"type": "tool_call", "name": fn_name, "args": fn_args, "call_id": tc.id}

                fn = TOOL_DISPATCH.get(fn_name)
                if fn:
                    result = fn(**fn_args)
                    # Track mentioned assets for working memory
                    if fn_name in ("list_assets", "search_assets") and isinstance(result, dict):
                        for asset in result.get("assets", []):
                            context.track_asset(asset.get("name", ""), asset.get("id", 0))
                    elif fn_name == "get_asset_history" and isinstance(result, dict):
                        a = result.get("asset", {})
                        if a:
                            context.track_asset(a.get("name", ""), a.get("id", 0))
                else:
                    result = {"error": f"Unknown tool: {fn_name}"}

                result_str = json.dumps(result)
                tool_call_count += 1
                yield {"type": "tool_result", "name": fn_name, "call_id": tc.id, "result": result}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

        elif choice.finish_reason == "stop":
            final_text = msg.content or ""
            # Store the clean final text in context (strip the working memory hint)
            context.add_assistant(final_text)
            # Update context messages to include any tool calls from this turn
            # (already captured in rolling `messages` list — sync back)
            _sync_turn_to_context(context, messages)

            yield {"type": "assistant_text", "content": final_text}

            usage = response.usage
            latency_ms = int((time.monotonic() - start) * 1000)
            tokens = (usage.total_tokens if usage else 0)
            yield {
                "type": "metrics",
                "latency_ms": latency_ms,
                "tokens": tokens,
                "tool_call_count": tool_call_count,
            }
            break
        else:
            # Unexpected finish reason
            break


def _sync_turn_to_context(context: ConversationContext, messages: list[dict]) -> None:
    """Replace context.messages with the full rolled-up messages from this turn."""
    # Strip the system message prepended in run_turn
    context.messages = [m for m in messages if m.get("role") != "system"]
