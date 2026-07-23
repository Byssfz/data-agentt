import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.agent.nodes.intent import IntentDecision, intent_recognition, tool_call_node


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

    def test_intent_emits_progress_and_decision_events(self):
        events = []
        llm_decision = IntentDecision(
            route="chat",
            intent="chat",
            confidence=0.98,
            answer="你好。",
            source="llm",
        )
        runtime = SimpleNamespace(
            context={"tool_registry": SimpleNamespace(list=lambda: [])},
            stream_writer=events.append,
        )
        state = {"query": "你好", "memory": {}}

        with patch("app.agent.nodes.intent._llm_fallback", new=AsyncMock(return_value=llm_decision)):
            asyncio.run(intent_recognition(state, runtime))

        self.assertEqual(
            [(event["type"], event["status"]) for event in events if event["type"] == "progress"],
            [("progress", "running"), ("progress", "success")],
        )
        self.assertEqual(events[1]["type"], "intent")

    def test_tool_route_accepts_null_answer(self):
        llm_decision = IntentDecision(
            route="tool_call",
            intent="text_to_sql",
            confidence=0.95,
            tool_name="data.query",
            arguments={"query": "查询销售额"},
            answer=None,
            source="llm",
        )
        runtime = SimpleNamespace(
            context={"tool_registry": SimpleNamespace(list=lambda: [])},
            stream_writer=lambda _: None,
        )
        state = {"query": "查询销售额", "memory": {}}

        with patch("app.agent.nodes.intent._llm_fallback", new=AsyncMock(return_value=llm_decision)):
            result = asyncio.run(intent_recognition(state, runtime))

        self.assertEqual(result["route"], "tool_call")
        self.assertEqual(result["route_answer"], "")

    def test_route_accepts_model_output_without_confidence(self):
        decision = IntentDecision.model_validate({
            "route": "chat",
            "answer": "你好！",
        })

        self.assertEqual(decision.confidence, 0.0)

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

    def test_tool_call_repairs_invalid_arguments_once(self):
        registry = SimpleNamespace(
            execute=AsyncMock(side_effect=[ValueError("missing query"), {"ok": True}]),
            list=lambda: [],
        )
        runtime = SimpleNamespace(
            context={"tool_registry": registry},
            stream_writer=lambda _: None,
        )
        state = {
            "query": "查询销售额",
            "tool_name": "data.query",
            "tool_arguments": {},
            "memory": {},
            "role": "user",
            "tool_retry_count": 0,
        }
        repaired = SimpleNamespace(tool_name="data.query", arguments={"query": "查询销售额"})

        with patch("app.agent.nodes.intent._repair_tool_call", new=AsyncMock(return_value=repaired)) as repair:
            result = asyncio.run(tool_call_node(state, runtime))

        repair.assert_awaited_once()
        self.assertEqual(result["response"], "{'ok': True}")
        self.assertEqual(registry.execute.await_count, 2)

    def test_query_tool_result_is_not_reemitted_as_a_duplicate_table(self):
        events = []
        registry = SimpleNamespace(
            execute=AsyncMock(return_value={"type": "query_result", "rows": [{"地区": "华东", "销售额": 10}]}),
            list=lambda: [],
        )
        runtime = SimpleNamespace(
            context={"tool_registry": registry},
            stream_writer=events.append,
        )
        state = {
            "query": "查询销售额",
            "tool_name": "data.query",
            "tool_arguments": {"query": "查询销售额"},
            "memory": {},
            "role": "user",
        }

        asyncio.run(tool_call_node(state, runtime))

        self.assertEqual(events[0], {"type": "progress", "step": "调用工具", "status": "running"})
        self.assertEqual(events[1]["type"], "tool_result")
        self.assertEqual(events[2], {"type": "progress", "step": "调用工具", "status": "success"})


if __name__ == "__main__":
    unittest.main()
