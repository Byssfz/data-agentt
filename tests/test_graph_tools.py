import unittest

from app.agent.graph import tool_registry


class RegisteredGraphToolsTests(unittest.TestCase):
    def test_initial_tool_catalog_contains_namespaced_query_tools(self):
        tools = {tool.name: tool for tool in tool_registry.list()}

        self.assertEqual(
            {"data.query", "result.export_excel", "chart.draw"}.issubset(tools),
            True,
        )
        self.assertEqual(tools["data.query"].kind, "graph")
        self.assertIsNotNone(tools["data.query"].handler)
        self.assertIsNotNone(tools["result.export_excel"].handler)
        self.assertIsNotNone(tools["chart.draw"].handler)


if __name__ == "__main__":
    unittest.main()
