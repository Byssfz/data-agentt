"""Minimal stdio MCP server used by the local drawing-tool smoke test."""

from mcp.server.fastmcp import FastMCP, Image

mcp = FastMCP("drawing-smoke")


@mcp.tool()
def draw_image(prompt: str, format: str = "png") -> Image:
    """Return a tiny image payload representing a generated drawing."""
    # The fixture uses a deterministic payload; a real drawing server can replace
    # this tool with an image model while keeping the same MCP contract.
    return Image(data=b"drawing-smoke-image", format=format)


if __name__ == "__main__":
    mcp.run(transport="stdio")
