import unittest

from app.core.intent import classify_with_rules


class IntentConfidenceTests(unittest.TestCase):
    def test_strong_rule_is_high_confidence(self):
        decision = classify_with_rules("查询本月销售总额")
        self.assertEqual(decision.intent, "text_to_sql")
        self.assertGreaterEqual(decision.confidence, 0.85)

    def test_ambiguous_query_is_low_confidence(self):
        decision = classify_with_rules("帮我看看这个")
        self.assertLess(decision.confidence, 0.85)
