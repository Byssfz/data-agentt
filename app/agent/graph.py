from __future__ import annotations

from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.nodes.add_extra_context import add_extra_context
from app.agent.nodes.corrtect_sql import correct_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.intent import (
    chat_node,
    clarification_node,
    history_query_node,
    intent_recognition,
    security_node,
    tool_call_node,
    unsupported_intent,
)
from app.agent.nodes.memory import load_memory
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.recall_value import recall_value
from app.agent.nodes.run_sql import run_sql
from app.agent.nodes.post_process_result import post_process_result
from app.agent.nodes.validate_sql import validate_sql
from app.agent.state import DataAgentState
from app.tools.registry import ToolRegistry, ToolDefinition
from app.tools.builtin import export_excel, mermaid_treemap, summarize_result


def build_sql_graph():
    builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)
    builder.add_node("extract_keywords", extract_keywords)
    builder.add_node("recall_column", recall_column)
    builder.add_node("recall_value", recall_value)
    builder.add_node("recall_metric", recall_metric)
    builder.add_node("merge_retrieved_info", merge_retrieved_info)
    builder.add_node("filter_metric", filter_metric)
    builder.add_node("filter_table", filter_table)
    builder.add_node("add_extra_context", add_extra_context)
    builder.add_node("generate_sql", generate_sql)
    builder.add_node("validate_sql", validate_sql)
    builder.add_node("correct_sql", correct_sql)
    builder.add_node("run_sql", run_sql)
    builder.add_edge(START, "extract_keywords")
    builder.add_edge("extract_keywords", "recall_column")
    builder.add_edge("extract_keywords", "recall_value")
    builder.add_edge("extract_keywords", "recall_metric")
    builder.add_edge("recall_column", "merge_retrieved_info")
    builder.add_edge("recall_value", "merge_retrieved_info")
    builder.add_edge("recall_metric", "merge_retrieved_info")
    builder.add_edge("merge_retrieved_info", "filter_metric")
    builder.add_edge("merge_retrieved_info", "filter_table")
    builder.add_edge("filter_metric", "add_extra_context")
    builder.add_edge("filter_table", "add_extra_context")
    builder.add_edge("add_extra_context", "generate_sql")
    builder.add_edge("generate_sql", "validate_sql")
    builder.add_conditional_edges(
        "validate_sql", lambda state: "run_sql" if state.get("error") is None else "correct_sql",
        {"run_sql": "run_sql", "correct_sql": "correct_sql"},
    )
    builder.add_edge("correct_sql", "run_sql")
    builder.add_edge("run_sql", END)
    return builder.compile()


sql_graph = build_sql_graph()
tool_registry = ToolRegistry()
tool_registry.register(ToolDefinition(
    name="data.query",
    description="Run a read-only natural language data query through the SQL agent subgraph.",
    handler=None,
    kind="graph",
    allowed_intents={"text_to_sql", "schema_query"},
))
tool_registry.register(ToolDefinition(
    name="export_excel",
    description="Export the current tabular query result to a downloadable Excel workbook.",
    handler=export_excel,
    input_schema={"type": "object", "properties": {
        "rows": {"type": "array"}, "title": {"type": "string"}
    }, "required": ["rows"]},
    allowed_intents={"text_to_sql", "schema_query"},
))
tool_registry.register(ToolDefinition(
    name="summarize_result",
    description="Summarize the current tabular query result with row count and numeric totals.",
    handler=summarize_result,
    input_schema={"type": "object", "properties": {"rows": {"type": "array"}}, "required": ["rows"]},
    allowed_intents={"text_to_sql", "schema_query"},
))
tool_registry.register(ToolDefinition(
    name="chart.to_mermaid_treemap",
    description="Convert regional label/value query rows into Mermaid treemap syntax.",
    handler=mermaid_treemap,
    input_schema={"type": "object", "properties": {
        "rows": {"type": "array"}, "label_column": {"type": "string"}, "value_column": {"type": "string"}
    }, "required": ["rows"]},
    allowed_intents={"text_to_sql", "schema_query", "tool_call"},
))


async def run_sql_subgraph(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    runtime.context["tool_registry"].authorize(
        "data.query", role=state.get("role", "user"), intent=state.get("intent", "")
    )
    result_state = {}
    result = None
    async for chunk in sql_graph.astream(state, context=runtime.context, stream_mode="custom"):
        writer(chunk)
        if chunk.get("type") == "result":
            result = chunk.get("data")
    result_state["response"] = "SQL 查询已完成，请查看上方结果。"
    result_state["result"] = result
    return result_state


def route_by_intent(state: DataAgentState) -> str:
    return state.get("intent", "unsupported")


outer_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)
outer_builder.add_node("load_memory", load_memory)
outer_builder.add_node("intent_recognition", intent_recognition)
outer_builder.add_node("run_sql_subgraph", run_sql_subgraph)
outer_builder.add_node("post_process_result", post_process_result)
outer_builder.add_node("chat", chat_node)
outer_builder.add_node("history_query", history_query_node)
outer_builder.add_node("security", security_node)
outer_builder.add_node("unsupported_intent", unsupported_intent)
outer_builder.add_node("clarification", clarification_node)
outer_builder.add_node("tool_call", tool_call_node)
outer_builder.add_edge(START, "load_memory")
outer_builder.add_edge("load_memory", "intent_recognition")
outer_builder.add_conditional_edges(
    "intent_recognition", route_by_intent,
    {
        "text_to_sql": "run_sql_subgraph",
        "schema_query": "run_sql_subgraph",
        "chat": "chat",
        "history_query": "history_query",
        "security": "security",
        "tool_call": "tool_call",
        "clarification": "clarification",
        "unsupported": "unsupported_intent",
    },
)
outer_builder.add_edge("run_sql_subgraph", "post_process_result")
outer_builder.add_edge("post_process_result", END)
outer_builder.add_edge("chat", END)
outer_builder.add_edge("history_query", END)
outer_builder.add_edge("security", END)
outer_builder.add_edge("unsupported_intent", END)
outer_builder.add_edge("clarification", END)
outer_builder.add_edge("tool_call", END)
graph = outer_builder.compile()
