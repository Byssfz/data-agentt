import unittest
from datetime import date
from decimal import Decimal

from app.core.intent import classify_intent
from app.memory import extract_long_term_memories
from app.services.query_service import _json_safe


class IntentMemoryTests(unittest.TestCase):
    def test_query_intents(self):
        self.assertEqual(classify_intent("统计本月销售总额"), "text_to_sql")
        self.assertEqual(classify_intent("我之前问过什么"), "history_query")
        self.assertEqual(classify_intent("有哪些表和字段"), "schema_query")

    def test_explicit_long_term_memory(self):
        memories = extract_long_term_memories("我喜欢用表格展示，以后都用中文")
        self.assertTrue(any(item["memory_type"] == "preference" for item in memories))
        self.assertTrue(all(item["content"] for item in memories))

    def test_database_values_are_json_safe_before_memory_persistence(self):
        result = _json_safe({
            "total_sales": Decimal("41099.5"),
            "total_quantity": Decimal("82"),
            "day": date(2026, 7, 23),
        })
        self.assertEqual(result, {
            "total_sales": 41099.5,
            "total_quantity": 82,
            "day": "2026-07-23",
        })
