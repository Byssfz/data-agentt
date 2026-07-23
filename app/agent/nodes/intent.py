from __future__ import annotations

import json
from typing import Literal

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.intent import INTENT_DESCRIPTIONS, RuleDecision, classify_with_rules
from app.conf.app_config import app_config


class IntentDecision(BaseModel):
    route: Literal["tool_call", "chat", "refuse"] = "tool_call"
    tool_name: str | None = None
    arguments: dict = Field(default_factory=dict)
    answer: str = ""
    intent: str = "tool_call"
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    alternatives: list[dict] = Field(default_factory=list)
    entities: dict = Field(default_factory=dict)
    source: str = "rule"


def _as_model(decision: RuleDecision) -> IntentDecision:
    return IntentDecision(
        intent=decision.intent,
        confidence=decision.confidence,
        reason=decision.reason,
        alternatives=decision.alternatives,
        entities=decision.entities,
        source=decision.source,
    )


def _memory_prompt(state: DataAgentState) -> str:
    memory = state.get("memory", {})
    return json.dumps({
        "working_memory": memory.get("working", [])[-app_config.intent.max_memory_messages:],
        "long_term_memory": memory.get("long_term", []),
    }, ensure_ascii=False, default=str)


async def _llm_fallback(state: DataAgentState, rule_decision: IntentDecision, tool_registry) -> IntentDecision:
    intent_list = "\n".join(f"- {name}: {description}" for name, description in INTENT_DESCRIPTIONS.items())
    tool_list = "\n".join(
        f"- {tool.name}: {tool.description}; schema={json.dumps(tool.input_schema, ensure_ascii=False)}"
        for tool in tool_registry.list()
    )
    prompt = f"""你是数据智能系统的统一路由器。请根据当前问题、会话历史和长期记忆，选择下一步处理方式。

只能返回以下三种 route 之一：
- tool_call：选择一个可用工具，并生成符合其 schema 的 arguments。
- chat：直接生成 answer，不调用工具。
- refuse：直接生成拒答 answer，不调用工具。

意图列表：
{intent_list}

当前问题：
{state['query']}

可参考的会话/长期记忆：
{_memory_prompt(state)}

最近一次查询的结构化结果（如果有，工具调用可直接使用）：
{json.dumps(state.get('memory', {}).get('latest_result'), ensure_ascii=False, default=str)}

可用工具：
{tool_list or '当前没有额外工具'}

规则分类结果（仅作参考）：
{rule_decision.model_dump_json(ensure_ascii=False)}

请只返回一个合法 JSON 对象，不要返回 Markdown 或额外说明。JSON 必须符合 IntentDecision 结构，confidence 必须是 0 到 1 之间的数。
当 route=tool_call 时，必须在 tool_name 中填写可用工具的完整名称，并在 arguments 中填写符合工具 schema 的参数；不要填写不存在的工具。
当 route=chat 或 route=refuse 时，填写 answer，不要调用工具。
"""
    methods = [app_config.intent.structured_output_method]
    if "json_mode" not in methods:
        # DeepSeek thinking models reject tool_choice/function_calling. JSON mode
        # keeps the structured contract without sending a tool choice.
        methods.append("json_mode")
    errors: list[str] = []
    for method in methods:
        try:
            try:
                structured_llm = llm.with_structured_output(IntentDecision, method=method)
            except TypeError:
                structured_llm = llm.with_structured_output(IntentDecision)
            decision = await structured_llm.ainvoke(prompt)
            if isinstance(decision, IntentDecision):
                return decision.model_copy(update={"source": "llm"})
            return IntentDecision.model_validate({**decision, "source": "llm"})
        except Exception as exc:
            errors.append(f"{method}: {exc}")
    if errors:
        error_message = "；".join(errors)
    else:
        error_message = "没有可用的结构化输出方式"
    return IntentDecision(
        route="chat", intent="clarification", confidence=0.0,
        answer="我暂时无法可靠判断你的需求，请补充说明。",
        reason=f"规则置信度不足且大模型路由失败：{error_message}", source="fallback",
    )


async def intent_recognition(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    rule_decision = _as_model(classify_with_rules(state["query"]))
    # Rules are only a cheap hint now. The LLM owns the final intent, tool,
    # and argument decision so follow-up requests keep one consistent contract.
    decision = await _llm_fallback(state, rule_decision, runtime.context["tool_registry"])
    entities = dict(decision.entities)
    tool_name = decision.tool_name or entities.get("tool_name")
    arguments = dict(decision.arguments or entities.get("arguments", {}))
    if decision.route == "tool_call" and not tool_name and decision.intent in {"text_to_sql", "schema_query"}:
        tool_name = "data.query"
        arguments = {"query": state["query"]}
    if tool_name:
        entities.update({"tool_name": tool_name, "arguments": arguments})
    runtime.stream_writer({
        "type": "intent",
        "route": decision.route,
        "intent": decision.intent,
        "confidence": decision.confidence,
        "source": decision.source,
        "reason": decision.reason,
        "alternatives": decision.alternatives,
        "entities": entities,
        "tool": tool_name,
    })
    return {
        "route": decision.route,
        "route_answer": decision.answer,
        "tool_name": tool_name or "",
        "tool_arguments": arguments,
        "intent": decision.intent,
        "intent_confidence": decision.confidence,
        "intent_source": decision.source,
        "intent_reason": decision.reason,
        "intent_alternatives": decision.alternatives,
        "intent_entities": entities,
    }


async def unsupported_intent(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = f"当前暂不支持意图：{state['intent']}"
    runtime.stream_writer({"type": "result", "data": message})
    return {"response": message}


async def clarification_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = "我暂时无法可靠判断你的需求。请说明是查询数据、查看历史、查看表结构，还是调用某个工具。"
    runtime.stream_writer({"type": "clarification", "data": message})
    return {"response": message}


async def refuse_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = state.get("route_answer") or "抱歉，这个请求超出了当前系统的处理范围。"
    runtime.stream_writer({"type": "result", "data": message})
    return {"response": message}


async def tool_call_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    tool_name = state.get("tool_name")
    if not tool_name:
        return await clarification_node(state, runtime)
    try:
        arguments = dict(state.get("tool_arguments", {}))
        if tool_name == "data.query":
            arguments.setdefault("query", state["query"])
            arguments.setdefault("user_id", state.get("user_id", "anonymous"))
            arguments.setdefault("session_id", state.get("session_id", ""))
        if tool_name in {"result.export_excel", "chart.draw", "export_excel", "draw_treemap"} and "rows" not in arguments:
            latest_result = state.get("memory", {}).get("latest_result")
            if isinstance(latest_result, list):
                arguments["rows"] = latest_result
        result = await runtime.context["tool_registry"].execute(
            tool_name, arguments,
            role=state.get("role", "user"), intent="tool_call",
            runtime=runtime,
        )
        runtime.stream_writer({"type": "tool_result", "tool": tool_name, "data": result})
        return {"response": str(result)}
    except Exception as exc:
        runtime.stream_writer({"type": "error", "message": str(exc)})
        return {"response": str(exc)}


async def chat_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = state.get("route_answer") or "你好，我可以帮助你查询数据、导出 Excel 或画图。"
    runtime.stream_writer({"type": "result", "data": message})
    return {"response": message}


async def history_query_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    history = state.get("memory", {}).get("working", [])
    message = {"type": "history", "data": history}
    runtime.stream_writer(message)
    return {"response": str(history)}


async def security_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = f"当前会话角色为 {state.get('role', 'user')}，工具权限由服务端配置控制。"
    runtime.stream_writer({"type": "result", "data": message})
    return {"response": message}
