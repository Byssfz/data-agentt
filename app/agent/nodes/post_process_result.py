from __future__ import annotations

import re

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


def _wants_chart(query: str) -> bool:
    return any(word in query.lower() for word in ("树状图", "treemap", "图表", "可视化", "画图"))


def _wants_excel(query: str) -> bool:
    lowered = query.lower()
    return any(word in lowered for word in ("excel", "xlsx", "表格文件", "导出表格"))


def _wants_summary(query: str) -> bool:
    return any(word in query for word in ("总结", "摘要", "概括", "说明结果"))


def _compact_mcp_result(result: dict) -> dict:
    """Keep only user-facing image/link data from verbose MCP responses."""
    content = result.get("content", [])
    images = [item for item in content if item.get("type") == "image"]
    text = "\n".join(item.get("text", "") for item in content if item.get("type") == "text")
    preview_match = re.search(r"https://mermaid\.ai/live/edit\?[^\s)]+", text)
    if images:
        image = images[0]
        return {
            "type": "image",
            "message": "树状图已生成",
            "mime_type": image.get("mime_type", "image/png"),
            "data": image.get("data", ""),
            "preview_url": preview_match.group(0) if preview_match else None,
        }
    return {
        "type": "text",
        "message": "树状图生成失败",
        "detail": text[:500] if text else "Mermaid MCP 没有返回详细错误。",
    }


async def post_process_result(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    result = state.get("result")
    query = state.get("query", "")
    if not isinstance(result, list) or not result:
        return {}

    registry = runtime.context["tool_registry"]
    role = state.get("role", "user")
    events: list[dict] = []

    if _wants_summary(query):
        summary = await registry.execute(
            "summarize_result", {"rows": result}, role=role, intent="text_to_sql"
        )
        event = {"type": "tool_result", "tool": "summarize_result", "data": summary}
        runtime.stream_writer(event)
        events.append(event)

    if _wants_excel(query):
        exported = await registry.execute(
            "export_excel",
            {"rows": result, "title": "Query Result"},
            role=role,
            intent="text_to_sql",
        )
        event = {"type": "tool_result", "tool": "export_excel", "data": exported}
        runtime.stream_writer(event)
        events.append(event)

    if _wants_chart(query):
        chart_input = await registry.execute(
            "chart.to_mermaid_treemap", {"rows": result}, role=role, intent="text_to_sql"
        )
        mcp_name = "mermaid.validate_and_render_mermaid_diagram"
        if mcp_name not in {tool.name for tool in registry.list()}:
            event = {"type": "error", "message": "Mermaid MCP 工具尚未连接，无法渲染树状图"}
            runtime.stream_writer(event)
            events.append(event)
        else:
            rendered = await registry.execute(
                mcp_name,
                {
                    "prompt": "请渲染各地区销售额树状图",
                    "mermaidCode": chart_input["mermaid_code"],
                    "diagramType": "treemap",
                    "clientName": "data-agentt",
                    "useUrlShortener": False,
                },
                role=role,
                intent="tool_call",
            )
            event = {"type": "tool_result", "tool": mcp_name, "data": _compact_mcp_result(rendered)}
            runtime.stream_writer(event)
            events.append(event)
    return {"post_process_events": events}
