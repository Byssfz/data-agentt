from __future__ import annotations

from typing import Any

from app.tools.registry import ToolDefinition, ToolRegistry


def _transport(config: dict[str, Any]):
    if config.get("transport", "stdio") == "stdio":
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        return stdio_client(StdioServerParameters(
            command=config["command"], args=config.get("args", []), env=config.get("env")
        ))
    if config.get("transport") == "sse":
        from mcp.client.sse import sse_client

        return sse_client(config["url"])
    raise ValueError(f"Unsupported MCP transport: {config.get('transport')}")


async def _call(config: dict[str, Any], name: str, arguments: dict[str, Any]):
    from mcp import ClientSession

    async with _transport(config) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.call_tool(name, arguments)
            return [getattr(item, "text", str(item)) for item in response.content]


async def register_mcp_servers(registry: ToolRegistry, servers: list[dict[str, Any]]) -> None:
    if not servers:
        return
    try:
        from mcp import ClientSession
    except ImportError as exc:
        raise RuntimeError("MCP servers are configured but the optional 'mcp' package is not installed") from exc

    for config in servers:
        async with _transport(config) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
                allowed = set(config.get("tools", []))
                for remote_tool in result.tools:
                    if allowed and remote_tool.name not in allowed:
                        continue
                    registry.register(ToolDefinition(
                        name=f"{config.get('name', 'mcp')}.{remote_tool.name}",
                        description=remote_tool.description or remote_tool.name,
                        handler=lambda args, c=config, n=remote_tool.name: _call(c, n, args),
                        input_schema=remote_tool.inputSchema or {},
                        kind="mcp",
                        allowed_roles=set(config.get("allowed_roles", ["admin"])),
                    ))
