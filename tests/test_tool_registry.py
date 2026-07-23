import asyncio
import unittest

from app.tools.registry import ToolDefinition, ToolRegistry


class ToolRegistryTests(unittest.TestCase):
    def test_register_and_execute_async_function(self):
        registry = ToolRegistry()

        async def add(arguments):
            return arguments["left"] + arguments["right"]

        registry.register(ToolDefinition(name="add", description="Add", handler=add))
        result = asyncio.run(registry.execute("add", {"left": 2, "right": 3}, role="user", intent="chat"))
        self.assertEqual(result, 5)

    def test_duplicate_registration_is_rejected(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="same", description="first"))
        with self.assertRaises(ValueError):
            registry.register(ToolDefinition(name="same", description="second"))

    def test_mutating_tool_requires_confirmation(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="write", description="Write", handler=lambda _: None, read_only=False))
        with self.assertRaises(PermissionError):
            asyncio.run(registry.execute("write", {}, role="user", intent="chat"))

    def test_intent_restriction_is_enforced(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="query", description="Query", handler=lambda _: 1,
                                          allowed_intents={"text_to_sql"}))
        with self.assertRaises(PermissionError):
            asyncio.run(registry.execute("query", {}, role="user", intent="chat"))

    def test_input_schema_is_validated_before_handler(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="sum",
            description="Sum",
            handler=lambda arguments: arguments["left"] + arguments["right"],
            input_schema={
                "type": "object",
                "properties": {"left": {"type": "integer"}, "right": {"type": "integer"}},
                "required": ["left", "right"],
                "additionalProperties": False,
            },
        ))
        with self.assertRaisesRegex(ValueError, "right"):
            asyncio.run(registry.execute("sum", {"left": 1}, role="user", intent="chat"))

    def test_invalid_input_schema_is_rejected(self):
        registry = ToolRegistry()
        with self.assertRaises(ValueError):
            registry.register(ToolDefinition(
                name="broken", description="Broken", input_schema={"type": "not-a-json-type"}
            ))


if __name__ == "__main__":
    unittest.main()
