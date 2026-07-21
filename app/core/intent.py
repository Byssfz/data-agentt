from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleDecision:
    intent: str
    confidence: float
    reason: str = ""
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    entities: dict[str, Any] = field(default_factory=dict)
    source: str = "rule"


INTENT_DESCRIPTIONS = {
    "chat": "闲聊、问候、一般解释，不需要查询数据库或调用工具",
    "schema_query": "询问数据库有哪些表、字段、表结构或元数据",
    "text_to_sql": "需要根据自然语言生成并执行只读 SQL 的数据查询",
    "history_query": "询问当前会话或过去的查询、对话历史",
    "security": "权限、安全、越权、敏感数据或工具访问问题",
    "tool_call": "明确要求调用某个外部工具或 MCP 工具",
    "clarification": "意图无法可靠判断，需要向用户澄清",
}


RULES: dict[str, tuple[tuple[str, float], ...]] = {
    "security": (("能不能访问", 0.98), ("权限", 0.97), ("越权", 0.99), ("敏感数据", 0.97), ("安全", 0.90)),
    "history_query": (("之前问过", 0.95), ("历史", 0.92), ("上次", 0.88), ("查询记录", 0.95)),
    "schema_query": (("表结构", 0.96), ("有哪些表", 0.95), ("字段", 0.86), ("列信息", 0.90), ("元数据", 0.95)),
    "text_to_sql": (("统计", 0.88), ("总额", 0.93), ("销售", 0.82), ("查询", 0.72), ("多少", 0.78), ("数量", 0.78)),
    "tool_call": (("调用工具", 0.96), ("使用 MCP", 0.98), ("执行工具", 0.95)),
}


def classify_with_rules(query: str) -> RuleDecision:
    scores = {
        intent: max((weight for phrase, weight in rules if phrase in query), default=0.0)
        for intent, rules in RULES.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_intent, best_score = ranked[0]
    if best_score == 0:
        return RuleDecision(
            intent="chat", confidence=0.45,
            reason="没有命中高确定性的规则，需交给大模型判断",
        )
    alternatives = [{"intent": name, "confidence": score} for name, score in ranked[1:] if score > 0]
    return RuleDecision(
        intent=best_intent, confidence=best_score,
        reason=f"命中规则：{best_intent}", alternatives=alternatives,
    )


def classify_intent(query: str) -> str:
    return classify_with_rules(query).intent
