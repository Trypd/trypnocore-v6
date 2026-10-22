"""opz-memory MCP server.

Bridges Claude Code (WSL) to OmegaPrimeZero's memory + trinket injection
system over the chat server's loopback HTTP API:

  remember(line)     -> POST /memory/remember  (explicit-note gates, dedupe)
  list_atoms()       -> GET  /memory/atoms     (all MeTTa memory claims)
  trinket_context(l) -> GET  /memory/context   (the injection block OPZ would
                        prepend for line: time, curated memories, reminders)

Stdio transport for Claude Code's MCP client. Stdlib HTTP only; the `mcp`
package supplies the protocol. Runs in WSL against Windows localhost
forwarding (127.0.0.1:8787 on the host).
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
import urllib.request

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

BASE = "http://127.0.0.1:8787"
# Pool slaves memory to this agent's bootstrap identity (fleet launcher sets it).
# Per-call pool argument overrides. Empty = the shared default store.
DEFAULT_POOL = os.environ.get("OPZ_POOL", "").strip() or None


def _get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


server = Server("opz-memory")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="remember",
            description=(
                "Store a memory in OmegaPrimeZero's MeTTa atom store. "
                "Use the operator's note shapes: 'remember that ...' or "
                "'remind me to ...'. Returns how many atoms were written."
            ),
            inputSchema={
                "type": "object",
                "properties": {"line": {"type": "string"}},
                "required": ["line"],
            },
        ),
        Tool(
            name="list_atoms",
            description=(
                "List every memory atom currently stored in OmegaPrimeZero's "
                "MeTTa store (episodic claims, insertion order)."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="trinket_context",
            description=(
                "Ask OmegaPrimeZero for the trinket memory-injection block it "
                "would prepend to a given line: absolute clock, curated "
                "memories selected for that line, reminders, curator status. "
                "Use before answering when shared continuity matters."
            ),
            inputSchema={
                "type": "object",
                "properties": {"line": {"type": "string"}},
                "required": ["line"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    pool = arguments.get("pool") or DEFAULT_POOL
    pool_q = f"pool={urllib.parse.quote(pool, safe='')}" if pool else ""
    if name == "remember":
        payload = {"line": arguments["line"]}
        if pool:
            payload["pool"] = pool
        result = _post("/memory/remember", payload)
        return [TextContent(type="text", text=json.dumps(result))]
    if name == "list_atoms":
        return [TextContent(type="text", text=json.dumps(_get(f"/memory/atoms{'?' + pool_q if pool_q else ''}")))]
    if name == "trinket_context":
        line = arguments.get("line", "")
        quoted = urllib.parse.quote(line, safe="")
        tail = f"line={quoted}" + (f"&{pool_q}" if pool_q else "")
        return [TextContent(type="text", text=json.dumps(_get(f"/memory/context?{tail}")))]
    raise ValueError(f"unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
