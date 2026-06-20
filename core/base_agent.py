"""BaseAgent: shared agent loop logic for all specialist agents."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from typing import Any, AsyncGenerator, Generator

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
from core.models import Provider, get_provider, resolve_model
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

            provider = get_provider()
            if provider == Provider.CLAUDE_CLI:
                final_text, total_tokens, tool_call_count = await self._run_cli(
                    user_message, context, events, span
                )
            elif provider == Provider.OPENROUTER:
                final_text, total_tokens, tool_call_count = await self._run_openrouter(
                    user_message, context, events, span
                )
            else:
                final_text, total_tokens, tool_call_count = await self._run_sdk(
                    user_message, context, events, span
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

    async def _run_sdk(
        self,
        user_message: str,
        context: ConversationContext,
        events: list[dict],
        span: Any,
    ) -> tuple[str, int, int]:
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

        return final_text, total_tokens, tool_call_count

    async def _run_cli(
        self,
        user_message: str,
        context: ConversationContext,
        events: list[dict],
        span: Any,
    ) -> tuple[str, int, int]:
        """Invoke the claude CLI as a subprocess with an stdio MCP server for tools."""
        mcp_config = {
            "mcpServers": {
                "home-assets": {
                    "command": sys.executable,
                    "args": ["-m", "tools.stdio_server"],
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(mcp_config, f)
            config_path = f.name

        try:
            cmd = [
                "claude",
                "--model", self.config.model,
                "--system-prompt", self._system_prompt + context.working_memory_hint,
                "--mcp-config", config_path,
                "--disallowedTools", "Bash,Write,Edit,MultiEdit,NotebookEdit,Read",
                "--max-turns", str(self.config.max_turns),
                "--output-format", "stream-json",
                "-p", context.format_prompt(user_message),
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            pending_tool_calls: dict[str, str] = {}
            final_text = ""
            total_tokens = 0
            tool_call_count = 0

            async for raw_line in proc.stdout:
                line = raw_line.decode().strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")

                if etype == "assistant":
                    msg = event.get("message", {})
                    for block in msg.get("content", []):
                        btype = block.get("type")
                        if btype == "text":
                            final_text = block.get("text", "")
                        elif btype == "tool_use":
                            tool_call_count += 1
                            call_id = block["id"]
                            tool_name = block["name"]
                            pending_tool_calls[call_id] = tool_name
                            span.add_event("tool_call", {"tool": tool_name})
                            events.append({
                                "type": "tool_call",
                                "name": tool_name,
                                "args": block.get("input", {}),
                                "call_id": call_id,
                            })
                    usage = msg.get("usage", {})
                    total_tokens = (
                        usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    )

                elif etype == "user":
                    for block in event.get("message", {}).get("content", []):
                        if block.get("type") == "tool_result":
                            call_id = block.get("tool_use_id", "")
                            tool_name = pending_tool_calls.get(call_id, "unknown")
                            result_content = block.get("content", "")
                            if isinstance(result_content, list):
                                result_content = " ".join(
                                    c.get("text", "")
                                    for c in result_content
                                    if c.get("type") == "text"
                                )
                            _update_working_memory(context, tool_name, result_content)
                            events.append({
                                "type": "tool_result",
                                "name": tool_name,
                                "call_id": call_id,
                                "result": result_content,
                            })

                elif etype == "result":
                    usage = event.get("usage", {})
                    total_tokens = (
                        usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    )

            await proc.wait()

        finally:
            os.unlink(config_path)

        return final_text, total_tokens, tool_call_count

    async def _run_openrouter(
        self,
        user_message: str,
        context: ConversationContext,
        events: list[dict],
        span: Any,
    ) -> tuple[str, int, int]:
        from openai import AsyncOpenAI
        from tools.mcp_server import dispatch_tool, get_openai_tool_schemas

        client = AsyncOpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            base_url="https://openrouter.ai/api/v1",
        )
        logical = "haiku" if "haiku" in self.config.model else "sonnet"
        model = resolve_model(logical)
        tool_schemas = get_openai_tool_schemas()

        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt + context.working_memory_hint},
            {"role": "user", "content": context.format_prompt(user_message)},
        ]

        final_text = ""
        total_tokens = 0
        tool_call_count = 0

        for _ in range(self.config.max_turns):
            resp = await client.chat.completions.create(
                model=model,
                max_tokens=4096,
                messages=messages,
                tools=tool_schemas,
            )

            if resp.usage:
                total_tokens += resp.usage.prompt_tokens + resp.usage.completion_tokens

            msg = resp.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                    tool_call_count += 1
                    span.add_event("tool_call", {"tool": tool_name})

                    events.append({
                        "type": "tool_call",
                        "name": tool_name,
                        "args": tool_args,
                        "call_id": tc.id,
                    })

                    try:
                        result = dispatch_tool(tool_name, tool_args)
                        result_str = json.dumps(result)
                    except Exception as exc:
                        result_str = json.dumps({"error": str(exc)})

                    _update_working_memory(context, tool_name, result_str)
                    events.append({
                        "type": "tool_result",
                        "name": tool_name,
                        "call_id": tc.id,
                        "result": result_str,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })
            else:
                final_text = msg.content or ""
                break

        return final_text, total_tokens, tool_call_count


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
