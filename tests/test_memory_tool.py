import asyncio
import unittest
from types import SimpleNamespace

from app.tools.builtin import save_long_term_memory


class MemoryToolTests(unittest.TestCase):
    def test_save_long_term_memory_uses_explicit_arguments(self):
        calls = []

        class Repository:
            async def remember_preference(self, **values):
                calls.append(values)

        runtime = SimpleNamespace(context={"memory_repository": Repository()})
        result = asyncio.run(save_long_term_memory(
            {"content": "以后用中文回答", "memory_type": "instruction", "user_id": "alice"},
            runtime=runtime,
        ))

        self.assertEqual(result["type"], "memory")
        self.assertEqual(calls, [{
            "user_id": "alice",
            "memory_type": "instruction",
            "content": "以后用中文回答",
        }])

    def test_empty_memory_content_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "content"):
            asyncio.run(save_long_term_memory({"content": "   "}, runtime=SimpleNamespace(context={})))


if __name__ == "__main__":
    unittest.main()
