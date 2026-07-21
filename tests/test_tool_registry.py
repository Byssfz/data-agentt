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


if __name__ == "__main__":
    unittest.main()
