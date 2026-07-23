import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.agent.nodes.intent import IntentDecision, intent_recognition


class IntentNodeTests(unittest.TestCase):
    def test_strong_rule_still_calls_llm_for_final_decision(self):
        llm_decision = IntentDecision(
            intent="tool_call",
            confidence=0.91,
            source="llm",
            entities={"tool_name": "export_excel", "arguments": {}},
        )
        runtime = SimpleNamespace(
            context={"tool_registry": SimpleNamespace(list=lambda: [])},
            stream_writer=lambda _: None,
        )
        state = {"query": "查询本月销售总额", "memory": {}}

        with patch("app.agent.nodes.intent._llm_fallback", new=AsyncMock(return_value=llm_decision)) as fallback:
            result = asyncio.run(intent_recognition(state, runtime))

        fallback.assert_awaited_once()
        self.assertEqual(result["intent"], "tool_call")
        self.assertEqual(result["intent_entities"]["tool_name"], "export_excel")

    def test_chat_route_keeps_model_answer(self):
        llm_decision = IntentDecision(
            route="chat",
            intent="chat",
            confidence=0.98,
            answer="你好，很高兴和你聊天。",
            source="llm",
        )
        runtime = SimpleNamespace(
            context={"tool_registry": SimpleNamespace(list=lambda: [])},
            stream_writer=lambda _: None,
        )
        state = {"query": "你好", "memory": {}}

        with patch("app.agent.nodes.intent._llm_fallback", new=AsyncMock(return_value=llm_decision)):
            result = asyncio.run(intent_recognition(state, runtime))

        self.assertEqual(result["route"], "chat")
        self.assertEqual(result["route_answer"], "你好，很高兴和你聊天。")

    def test_refuse_route_does_not_select_a_tool(self):
        llm_decision = IntentDecision(
            route="refuse",
            intent="refuse",
            confidence=0.99,
            answer="抱歉，我不能帮助完成这个请求。",
            source="llm",
        )
        runtime = SimpleNamespace(
            context={"tool_registry": SimpleNamespace(list=lambda: [])},
            stream_writer=lambda _: None,
        )
        state = {"query": "删除数据", "memory": {}}

        with patch("app.agent.nodes.intent._llm_fallback", new=AsyncMock(return_value=llm_decision)):
            result = asyncio.run(intent_recognition(state, runtime))

        self.assertEqual(result["route"], "refuse")
        self.assertEqual(result["tool_name"], "")


if __name__ == "__main__":
    unittest.main()
