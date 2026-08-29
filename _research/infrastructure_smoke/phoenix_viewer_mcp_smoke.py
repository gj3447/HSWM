# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastmcp-slim[client]==3.4.7",
# ]
# ///
"""Verify the deployed Phoenix VIEWER stdio surface without reading secrets."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


EXPECTED_TOOLS = {
    "describeSqlSchema",
    "executeSql",
    "getProjects",
    "getProject",
}
CLAIM_BOUNDARY = (
    "infrastructure smoke only; not HSWM cognition, causal credit, canonical "
    "admission, continuous learning, or efficacy evidence"
)


async def _main() -> int:
    launcher = Path.home() / ".local/libexec/hswm-phoenix-viewer-mcp"
    transport = StdioTransport(command=str(launcher), args=[])
    async with Client(transport) as client:
        tools = await client.list_tools()
        read = await client.call_tool(
            "executeSql", {"sql": "SELECT 1 AS read_probe", "row_limit": 1}
        )
        unsafe = await client.call_tool(
            "executeSql",
            {"sql": "CREATE TABLE hswm_mcp_forbidden(x INTEGER)"},
        )

    names = {tool.name for tool in tools}
    if names != EXPECTED_TOOLS:
        raise RuntimeError(f"unexpected tool surface: {sorted(names)}")
    if any(
        tool.annotations is None or not tool.annotations.readOnlyHint
        for tool in tools
    ):
        raise RuntimeError("every exposed tool must carry read-only annotations")
    read_value = read.structured_content or {}
    if read.is_error or read_value.get("rows") != [[1]]:
        raise RuntimeError("bounded analytics read probe failed")
    unsafe_value = unsafe.structured_content or {}
    unsafe_code = (unsafe_value.get("error") or {}).get("code")
    if unsafe.is_error or unsafe_code not in {"not_read_only", "unsupported_syntax"}:
        raise RuntimeError("unsafe SQL was not refused by the analytics admission gate")

    print(
        json.dumps(
            {
                "schema": "hswm-phoenix-viewer-mcp-smoke/v1",
                "claim_boundary": CLAIM_BOUNDARY,
                "status": "PASS",
                "tools": sorted(names),
                "read_probe_rows": 1,
                "unsafe_sql_code": unsafe_code,
                "mutation_tools_exposed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
