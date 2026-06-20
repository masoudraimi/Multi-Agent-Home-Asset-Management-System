"""Stdio MCP server for the Claude Code CLI provider.

The CLI provider spawns this as a subprocess via --mcp-config, so all 11 home-asset
tools are available to the claude binary without going through the in-process SDK server.

LLM_PROVIDER is forced to claude_sdk here so that any embedded LLM calls (e.g. the
review_asset_draft judge) use the Anthropic SDK directly rather than recursively
spawning another claude subprocess.
"""
from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("LLM_PROVIDER", "claude_sdk")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from tools.mcp_server import _OPENROUTER_TOOL_DEFS, dispatch_tool

_server = Server("home-assets")


@_server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=name,
            description=desc,
            inputSchema=schema_cls.model_json_schema(),
        )
        for name, desc, schema_cls in _OPENROUTER_TOOL_DEFS
    ]


@_server.call_tool()
async def _call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    result = dispatch_tool(name, arguments or {})
    return [types.TextContent(type="text", text=json.dumps(result))]


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await _server.run(
            read_stream,
            write_stream,
            _server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(_main())
