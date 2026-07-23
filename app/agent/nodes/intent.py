from __future__ import annotations

import json
from typing import Literal

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.intent import INTENT_DESCRIPTIONS, RuleDecision, classify_with_rules
from app.core.log import logger
from app.conf.app_config import app_config


class IntentDecision(BaseModel):
    route: Literal["tool_call", "chat", "refuse"] = "tool_call"
    tool_name: str | None = None
    arguments: dict = Field(default_factory=dict)
    answer: str | None = None
    intent: str = "tool_call"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    alternatives: list[dict] = Field(default_factory=list)
    entities: dict = Field(default_factory=dict)
    source: str = "rule"


class ToolCallDecision(BaseModel):
    tool_name: str
    arguments: dict = Field(default_factory=dict)


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
            logger.warning(f"意图路由结构化输出失败: method={method}, error={str(exc)}")
    if errors:
        error_message = "；".join(errors)
    else:
        error_message = "没有可用的结构化输出方式"
    return IntentDecision(
        route="chat", intent="clarification", confidence=0.0,
        answer="我暂时无法可靠判断你的需求，请补充说明。",
        reason=f"规则置信度不足且大模型路由失败：{error_message}", source="fallback",
    )


async def _repair_tool_call(state: DataAgentState, tool_name: str, arguments: dict,
                            error: str, tool_registry) -> ToolCallDecision:
    tool_list = "\n".join(
        f"- {tool.name}: {tool.description}; schema={json.dumps(tool.input_schema, ensure_ascii=False)}"
        for tool in tool_registry.list()
    )
    prompt = f"""你是工具参数修正器。原路由已经选择了工具，但服务端校验失败。

当前问题：
{state['query']}

会话和长期记忆：
{_memory_prompt(state)}

原工具：{tool_name}
原参数：{json.dumps(arguments, ensure_ascii=False, default=str)}
校验错误：{error}

可用工具：
{tool_list}

只返回合法 JSON，必须包含 tool_name 和 arguments。只能选择可用工具，并严格遵守工具 schema。不要解释原因。
"""
    methods = [app_config.intent.structured_output_method]
    if "json_mode" not in methods:
        methods.append("json_mode")
    errors: list[str] = []
    for method in methods:
        try:
            try:
                structured_llm = llm.with_structured_output(ToolCallDecision, method=method)
            except TypeError:
                structured_llm = llm.with_structured_output(ToolCallDecision)
            decision = await structured_llm.ainvoke(prompt)
            if isinstance(decision, ToolCallDecision):
                return decision
            return ToolCallDecision.model_validate(decision)
        except Exception as exc:
            errors.append(f"{method}: {exc}")
    raise ValueError("工具参数自动修正失败：" + "；".join(errors))


async def intent_recognition(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    step = "意图识别"
    writer({"type": "progress", "step": step, "status": "running"})
    try:
        rule_decision = _as_model(classify_with_rules(state["query"]))
        logger.info(f"规则意图分类: intent={rule_decision.intent}, confidence={rule_decision.confidence}")
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
        writer({
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
        writer({"type": "progress", "step": step, "status": "success"})
        logger.info(
            f"意图识别完成: route={decision.route}, intent={decision.intent}, "
            f"tool={tool_name}, confidence={decision.confidence}, source={decision.source}"
        )
        return {
            "route": decision.route,
            "route_answer": decision.answer or "",
            "tool_name": tool_name or "",
            "tool_arguments": arguments,
            "intent": decision.intent,
            "intent_confidence": decision.confidence,
            "intent_source": decision.source,
            "intent_reason": decision.reason,
            "intent_alternatives": decision.alternatives,
            "intent_entities": entities,
        }
    except Exception as exc:
        writer({"type": "progress", "step": step, "status": "error"})
        logger.error(f"意图识别失败: {str(exc)}")
        raise


async def unsupported_intent(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    step = "不支持意图"
    runtime.stream_writer({"type": "progress", "step": step, "status": "running"})
    message = f"当前暂不支持意图：{state['intent']}"
    runtime.stream_writer({"type": "result", "data": message})
    runtime.stream_writer({"type": "progress", "step": step, "status": "success"})
    logger.info(f"不支持的意图: {state['intent']}")
    return {"response": message}


async def clarification_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    step = "澄清需求"
    runtime.stream_writer({"type": "progress", "step": step, "status": "running"})
    message = "我暂时无法可靠判断你的需求。请说明是查询数据、查看历史、查看表结构，还是调用某个工具。"
    runtime.stream_writer({"type": "clarification", "data": message})
    runtime.stream_writer({"type": "progress", "step": step, "status": "success"})
    logger.info("请求需要澄清")
    return {"response": message}


async def refuse_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    step = "拒绝回答"
    runtime.stream_writer({"type": "progress", "step": step, "status": "running"})
    message = state.get("route_answer") or "抱歉，这个请求超出了当前系统的处理范围。"
    runtime.stream_writer({"type": "result", "data": message})
    runtime.stream_writer({"type": "progress", "step": step, "status": "success"})
    logger.info(f"拒绝回答: intent={state.get('intent', '')}")
    return {"response": message}


async def tool_call_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    tool_name = state.get("tool_name")
    if not tool_name:
        return await clarification_node(state, runtime)
    step = "调用工具"
    runtime.stream_writer({"type": "progress", "step": step, "status": "running"})
    logger.info(f"开始调用工具: {tool_name}")
    try:
        arguments = dict(state.get("tool_arguments", {}))
        if tool_name == "data.query":
            arguments.setdefault("query", state["query"])
            arguments.setdefault("user_id", state.get("user_id", "anonymous"))
            arguments.setdefault("session_id", state.get("session_id", ""))
        if tool_name == "memory.save":
            arguments.setdefault("user_id", state.get("user_id", "anonymous"))
        if tool_name in {"result.export_excel", "chart.draw", "export_excel", "draw_treemap"} and "rows" not in arguments:
            latest_result = state.get("memory", {}).get("latest_result")
            if isinstance(latest_result, list):
                arguments["rows"] = latest_result
        try:
            result = await runtime.context["tool_registry"].execute(
                tool_name, arguments,
                role=state.get("role", "user"), intent="tool_call",
                runtime=runtime,
            )
        except (KeyError, ValueError) as exc:
            if state.get("tool_retry_count", 0) >= 1:
                raise
            repaired = await _repair_tool_call(
                state, tool_name, arguments, str(exc), runtime.context["tool_registry"]
            )
            result = await runtime.context["tool_registry"].execute(
                repaired.tool_name, repaired.arguments,
                role=state.get("role", "user"), intent="tool_call",
                runtime=runtime,
            )
            tool_name = repaired.tool_name

        runtime.stream_writer({"type": "tool_result", "tool": tool_name, "data": result})
        runtime.stream_writer({"type": "progress", "step": step, "status": "success"})
        logger.info(f"工具调用完成: {tool_name}")
        return {"response": str(result)}
    except Exception as exc:
        runtime.stream_writer({"type": "progress", "step": step, "status": "error"})
        runtime.stream_writer({"type": "error", "message": str(exc)})
        logger.error(f"工具调用失败: tool={tool_name}, error={str(exc)}")
        return {"response": str(exc)}


async def chat_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    step = "闲聊回复"
    runtime.stream_writer({"type": "progress", "step": step, "status": "running"})
    message = state.get("route_answer") or "你好，我可以帮助你查询数据、导出 Excel 或画图。"
    runtime.stream_writer({"type": "result", "data": message})
    runtime.stream_writer({"type": "progress", "step": step, "status": "success"})
    logger.info("闲聊回复完成")
    return {"response": message}


async def history_query_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    step = "查询历史"
    runtime.stream_writer({"type": "progress", "step": step, "status": "running"})
    history = state.get("memory", {}).get("working", [])
    message = {"type": "history", "data": history}
    runtime.stream_writer(message)
    runtime.stream_writer({"type": "progress", "step": step, "status": "success"})
    logger.info(f"历史查询完成: count={len(history)}")
    return {"response": str(history)}


async def security_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    step = "检查权限"
    runtime.stream_writer({"type": "progress", "step": step, "status": "running"})
    message = f"当前会话角色为 {state.get('role', 'user')}，工具权限由服务端配置控制。"
    runtime.stream_writer({"type": "result", "data": message})
    runtime.stream_writer({"type": "progress", "step": step, "status": "success"})
    logger.info(f"权限信息已返回: role={state.get('role', 'user')}")
    return {"response": message}
