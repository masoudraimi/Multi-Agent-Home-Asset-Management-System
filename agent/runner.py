"""Agent runner using the claude-agent-sdk agentic loop."""

from __future__ import annotations

import asyncio
import time
from typing import Generator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)

from agent.context import ConversationContext
from agent.system_prompt import get_system_prompt
from tools.mcp_server import build_sdk_server

MODEL = "claude-sonnet-4-6"


def _build_options(context: ConversationContext) -> ClaudeAgentOptions:
    system = get_system_prompt() + context.working_memory_hint
    return ClaudeAgentOptions(
        model=MODEL,
        system_prompt=system,
        permission_mode="bypassPermissions",
        mcp_servers={"home-assets": build_sdk_server()},
        disallowed_tools=["Bash", "Edit", "Write", "MultiEdit", "NotebookEdit", "Read"],
        max_turns=25,
    )


def run_turn(
    user_message: str,
    context: ConversationContext,
) -> Generator[dict, None, None]:
    """Run one conversation turn. Yields events for the UI to render.

    Event types:
      {"type": "tool_call", "name": str, "args": dict, "call_id": str}
      {"type": "tool_result", "name": str, "call_id": str, "result": str}
      {"type": "assistant_text", "content": str}
      {"type": "metrics", "latency_ms": int, "tokens": int, "tool_call_count": int}
    """
    events: list[dict] = []
    asyncio.run(_run_async(user_message, context, events))
    yield from events


async def _run_async(
    user_message: str,
    context: ConversationContext,
    events: list[dict],
) -> None:
    start = time.monotonic()
    options = _build_options(context)
    tool_call_count = 0
    final_text = ""
    total_tokens = 0

    # Build the prompt — include conversation history as context prefix if needed
    prompt = context.format_prompt(user_message)

    # Track tool call names for working memory updates
    pending_tool_calls: dict[str, str] = {}  # call_id → tool_name

    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    final_text = block.text

                elif isinstance(block, ThinkingBlock):
                    pass  # Thinking blocks not surfaced in UI

                elif isinstance(block, ToolUseBlock):
                    tool_call_count += 1
                    pending_tool_calls[block.id] = block.name
                    events.append({
                        "type": "tool_call",
                        "name": block.name,
                        "args": block.input,
                        "call_id": block.id,
                    })

                elif isinstance(block, ToolResultBlock):
                    tool_name = pending_tool_calls.get(block.tool_use_id, "unknown")
                    result_content = block.content or ""

                    # Update working memory when assets are returned
                    _update_working_memory(context, tool_name, result_content)

                    events.append({
                        "type": "tool_result",
                        "name": tool_name,
                        "call_id": block.tool_use_id,
                        "result": result_content,
                    })

            if msg.usage:
                total_tokens = (
                    msg.usage.get("input_tokens", 0) + msg.usage.get("output_tokens", 0)
                )

        elif isinstance(msg, ResultMessage):
            if msg.usage:
                total_tokens = (
                    msg.usage.get("input_tokens", 0) + msg.usage.get("output_tokens", 0)
                )

    if final_text:
        context.add_turn(user_message, final_text)
        events.append({"type": "assistant_text", "content": final_text})

    latency_ms = int((time.monotonic() - start) * 1000)
    events.append({
        "type": "metrics",
        "latency_ms": latency_ms,
        "tokens": total_tokens,
        "tool_call_count": tool_call_count,
    })


def _update_working_memory(context: ConversationContext, tool_name: str, result) -> None:
    """Extract asset IDs from tool results and add to working memory."""
    import json
    try:
        data = json.loads(result) if isinstance(result, str) else result
    except (json.JSONDecodeError, TypeError):
        return

    if not isinstance(data, dict):
        return

    if tool_name in ("list_assets", "search_assets"):
        for asset in data.get("assets", []):
            if isinstance(asset, dict):
                context.track_asset(asset.get("name", ""), asset.get("id", 0))

    elif tool_name == "get_asset_history":
        asset = data.get("asset", {})
        if isinstance(asset, dict):
            context.track_asset(asset.get("name", ""), asset.get("id", 0))

    elif tool_name == "add_asset":
        if data.get("status") == "created":
            context.track_asset(data.get("name", ""), data.get("asset_id", 0))
