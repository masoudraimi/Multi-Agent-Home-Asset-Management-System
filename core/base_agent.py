"""BaseAgent: shared agent loop logic for all specialist agents.

Each specialist agent (AssetAgent, MaintenanceAgent, InsightsAgent) extends this
class and provides its own agent name. The base class handles:
- Loading config from agent.yaml via AgentRegistry
- Reading system prompt from prompts/system.md
- Guardrail checks on input
- OTel span creation around each turn
- The claude-agent-sdk query() loop
- Working memory updates
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncGenerator, Generator

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

from datetime import date

from core.guardrails import Guardrails
from core.memory.short_term import ConversationContext
from core.observability import get_tracer
from core.registry import AgentRegistry
from tools.mcp_server import build_sdk_server


class BaseAgent:
    agent_name: str = ""

    def __init__(self) -> None:
        self.config = AgentRegistry().get(self.agent_name)
        self.tracer = get_tracer(self.agent_name)
        self.guardrails = Guardrails(self.config.guardrails)
        prompt_path = self.config.yaml_path.parent / "prompts" / "system.md"
        raw_prompt = prompt_path.read_text()
        self._system_prompt: str = raw_prompt.replace("{today}", date.today().isoformat())

    def run_turn(
        self,
        user_message: str,
        context: ConversationContext | None = None,
    ) -> Generator[dict, None, None]:
        """Synchronous generator yielding UI events. Wraps the async loop."""
        if context is None:
            context = ConversationContext()
        events: list[dict] = []
        asyncio.run(self._run_async(user_message, context, events))
        yield from events

    async def run_turn_async(
        self,
        user_message: str,
        context: ConversationContext | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Async generator yielding UI events, used by OrchestratorAgent."""
        if context is None:
            context = ConversationContext()
        events: list[dict] = []
        await self._run_async(user_message, context, events)
        for event in events:
            yield event

    async def _run_async(
        self,
        user_message: str,
        context: ConversationContext,
        events: list[dict],
    ) -> None:
        if self.guardrails.is_injected(user_message):
            events.append({"type": "assistant_text", "content": "I cannot process that request."})
            return

        with self.tracer.start_as_current_span(f"{self.agent_name}.run_turn") as span:
            span.set_attribute("agent_name", self.agent_name)
            span.set_attribute("model", self.config.model)

            start = time.monotonic()
            system = self._system_prompt + context.working_memory_hint
            options = ClaudeAgentOptions(
                model=self.config.model,
                system_prompt=system,
                permission_mode="bypassPermissions",
                mcp_servers={"home-assets": build_sdk_server()},
                disallowed_tools=["Bash", "Edit", "Write", "MultiEdit", "NotebookEdit", "Read"],
                max_turns=self.config.max_turns,
            )

            prompt = context.format_prompt(user_message)
            pending_tool_calls: dict[str, str] = {}
            final_text = ""
            total_tokens = 0
            tool_call_count = 0

            async for msg in query(prompt=prompt, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            final_text = block.text

                        elif isinstance(block, ThinkingBlock):
                            pass

                        elif isinstance(block, ToolUseBlock):
                            tool_call_count += 1
                            pending_tool_calls[block.id] = block.name
                            span.add_event("tool_call", {"tool": block.name})
                            events.append({
                                "type": "tool_call",
                                "name": block.name,
                                "args": block.input,
                                "call_id": block.id,
                            })

                        elif isinstance(block, ToolResultBlock):
                            tool_name = pending_tool_calls.get(block.tool_use_id, "unknown")
                            result_content = block.content or ""
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
                sanitized = self.guardrails.sanitize_output(final_text)
                context.add_turn(user_message, sanitized)
                events.append({"type": "assistant_text", "content": sanitized})

            latency_ms = int((time.monotonic() - start) * 1000)
            span.set_attribute("latency_ms", latency_ms)
            span.set_attribute("tokens", total_tokens)
            span.set_attribute("tool_calls", tool_call_count)

            events.append({
                "type": "metrics",
                "latency_ms": latency_ms,
                "tokens": total_tokens,
                "tool_call_count": tool_call_count,
                "agent": self.agent_name,
            })


def _update_working_memory(context: ConversationContext, tool_name: str, result: object) -> None:
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
