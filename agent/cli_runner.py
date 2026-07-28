"""Claude Code CLI subprocess dispatch.

Used when `LLM_PROVIDER=claude_cli`. Bypasses LangGraph — the CLI runs its
own agent loop with OAuth-based auth (no API key needed) and consumes our
tools via the stdio MCP server in `tools/stdio_server.py`.

Emits the same UI event dict shape as the LangGraph adapter so
`rxapp/state.py` consumes both paths uniformly:
    {"type": "routing", "agents": ["cli"]}
    {"type": "tool_call", ...}
    {"type": "tool_result", ...}
    {"type": "assistant_text", ...}
    {"type": "pending_approval", ...}   (via EventBus)
    {"type": "metrics", ...}
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.memory.short_term import ConversationContext
from core.metrics import TurnSummary, record_turn
from core.models import resolve_model
from core.registry import AgentRegistry
from core.session import USER_ID_ENV_VAR, get_current_user_id_or_none

log = get_logger(__name__)

_ASSET_PROMPT = Path(__file__).parent.parent / "agents" / "asset" / "prompts" / "system.md"


def _load_prompt() -> str:
    from datetime import date
    raw = _ASSET_PROMPT.read_text(encoding="utf-8")
    return raw.replace("{today}", date.today().isoformat())


async def run_cli_turn(
    user_message: str,
    context: ConversationContext,
) -> list[dict]:
    """Invoke Claude Code CLI as an agent, streaming events for the UI."""
    events: list[dict] = [{"type": "routing", "agents": ["cli"]}]
    if shutil.which("claude") is None:
        events.append({
            "type": "assistant_text",
            "content": "⚠ Configuration error: `claude` CLI not found on PATH. Install Claude Code, then run `claude auth login`.",
        })
        events.append(_metrics(0, 0, 0))
        return events

    user_id = get_current_user_id_or_none() or ""
    config = AgentRegistry().get("asset")
    model = resolve_model("sonnet")
    system_prompt = _load_prompt()

    # Approval events published by workflows/deletion.py go through the
    # legacy EventBus; drain the queue after the subprocess returns.
    from core.event_bus import EventBus
    from core.events import HumanApprovalRequested

    approval_queue: asyncio.Queue = asyncio.Queue()
    bus = EventBus()
    bus.subscribe_async(HumanApprovalRequested, approval_queue)

    # Build ephemeral MCP config + settings file for the CLI subprocess.
    mcp_config = {
        "mcpServers": {
            "home-assets": {
                "command": sys.executable,
                "args": ["-m", "tools.stdio_server"],
                "env": {**os.environ, USER_ID_ENV_VAR: user_id},
            }
        }
    }
    cli_settings = {"permissions": {"allow": ["mcp__home-assets"]}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(mcp_config, f)
        mcp_path = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(cli_settings, f)
        settings_path = f.name

    tool_calls: list[dict] = []
    final_text = ""
    total_tokens = 0
    t0 = time.monotonic()
    try:
        cmd = [
            "claude",
            "--model", model,
            "--system-prompt", system_prompt + _memory_hint(context),
            "--mcp-config", mcp_path,
            "--settings", settings_path,
            "--disallowedTools", "Bash,Write,Edit,MultiEdit,NotebookEdit,Read",
            "--max-turns", str(config.max_turns),
            "--output-format", "stream-json",
            "--verbose",
            "-p", _format_prompt(context, user_message),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        pending: dict[str, str] = {}                  # call_id -> tool_name

        async for raw_line in proc.stdout:            # type: ignore[union-attr]
            line = raw_line.decode(errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")
            if etype == "assistant":
                msg = event.get("message", {})
                for block in msg.get("content", []) or []:
                    btype = block.get("type")
                    if btype == "text":
                        final_text = block.get("text", "")
                    elif btype == "tool_use":
                        call_id = block["id"]
                        tool_name = block["name"]
                        pending[call_id] = tool_name
                        tc = {
                            "type": "tool_call",
                            "name": _strip_mcp_prefix(tool_name),
                            "args": block.get("input", {}) or {},
                            "call_id": call_id,
                        }
                        tool_calls.append(tc)
                        events.append(tc)
                usage = msg.get("usage", {}) or {}
                total_tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))

            elif etype == "user":
                for block in event.get("message", {}).get("content", []) or []:
                    if block.get("type") == "tool_result":
                        call_id = block.get("tool_use_id", "")
                        content = block.get("content", "")
                        if isinstance(content, list):
                            content = " ".join(
                                c.get("text", "") for c in content
                                if isinstance(c, dict) and c.get("type") == "text"
                            )
                        events.append({
                            "type": "tool_result",
                            "name": _strip_mcp_prefix(pending.get(call_id, "")),
                            "call_id": call_id,
                            "result": content,
                        })

            elif etype == "result":
                usage = event.get("usage", {}) or {}
                total_tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))

        await proc.wait()
        if proc.returncode not in (0, None):
            stderr = (await proc.stderr.read()).decode(errors="replace") if proc.stderr else ""
            log.error("claude_cli_nonzero_exit", code=proc.returncode, stderr=stderr[:500])
            if not final_text:
                final_text = f"⚠ Claude CLI exited with code {proc.returncode}."

    except FileNotFoundError:
        final_text = "⚠ `claude` executable not found. Install Claude Code CLI."
    except Exception:
        log.exception("cli_runner_failed")
        final_text = final_text or "Sorry — I hit an internal error. Please try again."
    finally:
        try:
            bus._async_queues[HumanApprovalRequested].remove(approval_queue)
        except (ValueError, KeyError):
            pass
        for p in (mcp_path, settings_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    # Drain any approvals the tool calls published.
    while not approval_queue.empty():
        ap = approval_queue.get_nowait()
        events.append({
            "type": "pending_approval",
            "request_id": ap.request_id,
            "agent_name": ap.agent_name,
            "action_description": ap.action_description,
            "payload_str": json.dumps(ap.payload, indent=2),
            "action": "delete_asset",
            "thread_id": "",         # empty ⇒ Reflex resumes via sentinel path
        })

    if final_text:
        events.append({"type": "assistant_text", "content": final_text})
        context.add_turn(user_message, final_text)

    duration_s = time.monotonic() - t0
    record_turn(TurnSummary(
        ts=time.time(), request_id="", user_id=user_id, agent="cli",
        provider="claude_cli", outcome="ok" if final_text else "error",
        duration_s=duration_s, cost_usd=0.0,
        tool_calls=len(tool_calls), tokens_in=0, tokens_out=0,
    ))
    events.append(_metrics(total_tokens, len(tool_calls), int(duration_s * 1000)))
    return events


def _strip_mcp_prefix(tool_name: str) -> str:
    """MCP tools come through as 'mcp__home-assets__<name>' — strip for display."""
    prefix = "mcp__home-assets__"
    return tool_name[len(prefix):] if tool_name.startswith(prefix) else tool_name


def _memory_hint(context: ConversationContext) -> str:
    return context.working_memory_hint


def _format_prompt(context: ConversationContext, user_message: str) -> str:
    return context.format_prompt(user_message)


def _metrics(tokens: int, tool_calls: int, latency_ms: int) -> dict:
    return {
        "type": "metrics",
        "latency_ms": latency_ms,
        "tokens": tokens,
        "tool_call_count": tool_calls,
        "agent": "cli",
    }
