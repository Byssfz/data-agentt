from __future__ import annotations

import json

from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.intent import INTENT_DESCRIPTIONS, RuleDecision, classify_with_rules


class IntentDecision(BaseModel):
    intent: str
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


RULE_CONFIDENCE_THRESHOLD = 0.85


def _memory_prompt(state: DataAgentState) -> str:
    memory = state.get("memory", {})
    return json.dumps({
        "working_memory": memory.get("working", [])[-10:],
        "long_term_memory": memory.get("long_term", []),
    }, ensure_ascii=False, default=str)


async def _llm_fallback(state: DataAgentState, rule_decision: IntentDecision, tool_registry) -> IntentDecision:
    intent_list = "\n".join(f"- {name}: {description}" for name, description in INTENT_DESCRIPTIONS.items())
    tool_list = "\n".join(f"- {tool.name}: {tool.description}" for tool in tool_registry.list())
    prompt = f"""你是数据智能系统的意图路由器。请只从给定意图中选择一个，不要执行工具。

意图列表：
{intent_list}

当前问题：
{state['query']}

可参考的会话/长期记忆：
{_memory_prompt(state)}

可用工具：
{tool_list or '当前没有额外工具'}

规则分类结果（仅作参考）：
{rule_decision.model_dump_json(ensure_ascii=False)}

请返回结构化结果，confidence 必须是 0 到 1 之间的数。若无法确定，选择 clarification。
"""
    try:
        structured_llm = llm.with_structured_output(IntentDecision)
        decision = await structured_llm.ainvoke(prompt)
        if isinstance(decision, IntentDecision):
            return decision.model_copy(update={"source": "llm"})
        return IntentDecision.model_validate({**decision, "source": "llm"})
    except Exception as exc:
        return IntentDecision(
            intent="clarification", confidence=0.0,
            reason=f"规则置信度不足且大模型路由失败：{exc}", source="fallback",
        )


async def intent_recognition(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    rule_decision = _as_model(classify_with_rules(state["query"]))
    if rule_decision.confidence >= RULE_CONFIDENCE_THRESHOLD:
        decision = rule_decision
    else:
        decision = await _llm_fallback(state, rule_decision, runtime.context["tool_registry"])
    runtime.stream_writer({
        "type": "intent",
        "intent": decision.intent,
        "confidence": decision.confidence,
        "source": decision.source,
        "reason": decision.reason,
        "alternatives": decision.alternatives,
        "entities": decision.entities,
    })
    return {
        "intent": decision.intent,
        "intent_confidence": decision.confidence,
        "intent_source": decision.source,
        "intent_reason": decision.reason,
        "intent_alternatives": decision.alternatives,
        "intent_entities": decision.entities,
    }


async def unsupported_intent(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = f"当前暂不支持意图：{state['intent']}"
    runtime.stream_writer({"type": "result", "data": message})
    return {"response": message}


async def clarification_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = "我暂时无法可靠判断你的需求。请说明是查询数据、查看历史、查看表结构，还是调用某个工具。"
    runtime.stream_writer({"type": "clarification", "data": message})
    return {"response": message}


async def tool_call_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    entities = state.get("intent_entities", {})
    tool_name = entities.get("tool_name")
    if not tool_name:
        return await clarification_node(state, runtime)
    try:
        result = await runtime.context["tool_registry"].execute(
            tool_name, entities.get("arguments", {}),
            role=state.get("role", "user"), intent="tool_call",
        )
        runtime.stream_writer({"type": "tool_result", "tool": tool_name, "data": result})
        return {"response": str(result)}
    except Exception as exc:
        runtime.stream_writer({"type": "error", "message": str(exc)})
        return {"response": str(exc)}


async def chat_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = "你好，我可以帮助你查询数据、查看历史会话或解释当前支持的功能。"
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
