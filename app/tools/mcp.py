from __future__ import annotations

from typing import Any

from loguru import logger

from app.tools.registry import ToolDefinition, ToolRegistry


def _streams(transport_result: Any) -> tuple[Any, Any]:
    """Extract the message streams from MCP transports across client versions."""
    if not isinstance(transport_result, tuple) or len(transport_result) < 2:
        raise RuntimeError("MCP transport did not return readable and writable streams")
    return transport_result[0], transport_result[1]


def normalize_mcp_content(item: Any) -> dict[str, Any]:
    """Convert MCP content blocks into JSON-safe application results.

    Image blocks keep their base64 payload and MIME type so drawing/image tools
    can be forwarded through the existing SSE response without losing data.
    """
    item_type = getattr(item, "type", None)
    if item_type == "text" or hasattr(item, "text"):
        return {"type": "text", "text": getattr(item, "text", "")}
    if item_type == "image" or hasattr(item, "data"):
        return {
            "type": "image",
            "mime_type": getattr(item, "mimeType", getattr(item, "mime_type", "application/octet-stream")),
            "data": getattr(item, "data", ""),
        }
    if item_type == "resource" or hasattr(item, "resource"):
        resource = getattr(item, "resource", None)
        return {
            "type": "resource",
            "resource": {
                "uri": getattr(resource, "uri", None),
                "mime_type": getattr(resource, "mimeType", getattr(resource, "mime_type", None)),
                "text": getattr(resource, "text", None),
                "blob": getattr(resource, "blob", None),
            },
        }
    return {"type": str(item_type or "unknown"), "value": str(item)}


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
    if config.get("transport") in {"http", "streamable_http"}:
        from mcp.client.streamable_http import streamable_http_client

        return streamable_http_client(config["url"])
    raise ValueError(f"Unsupported MCP transport: {config.get('transport')}")


async def _call(config: dict[str, Any], name: str, arguments: dict[str, Any]):
    from mcp import ClientSession

    async with _transport(config) as transport_result:
        read_stream, write_stream = _streams(transport_result)
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.call_tool(name, arguments)
            return {
                "is_error": bool(getattr(response, "isError", False)),
                "content": [normalize_mcp_content(item) for item in response.content],
            }


async def register_mcp_servers(registry: ToolRegistry, servers: list[dict[str, Any]]) -> None:
    if not servers:
        return
    try:
        from mcp import ClientSession
    except ImportError as exc:
        raise RuntimeError("MCP servers are configured but the optional 'mcp' package is not installed") from exc

    for config in servers:
        server_name = str(config.get("name", "mcp"))
        try:
            async with _transport(config) as transport_result:
                read_stream, write_stream = _streams(transport_result)
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    allowed = set(config.get("tools", []))
                    for remote_tool in result.tools:
                        if allowed and remote_tool.name not in allowed:
                            continue
                        registry.register(ToolDefinition(
                            name=f"{server_name}.{remote_tool.name}",
                            description=remote_tool.description or remote_tool.name,
                            handler=lambda args, c=config, n=remote_tool.name: _call(c, n, args),
                            input_schema=remote_tool.inputSchema or {},
                            kind="mcp",
                            read_only=bool(config.get("read_only", True)),
                            allowed_roles=set(config.get("allowed_roles", ["admin"])),
                            allowed_intents=set(config.get("allowed_intents", [])),
                            timeout_seconds=float(config.get("timeout_seconds", 60)),
                        ))
        except Exception:
            logger.exception("MCP server '{}' failed during startup; continuing without its tools", server_name)
