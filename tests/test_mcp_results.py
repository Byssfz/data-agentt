import unittest
from types import SimpleNamespace

from app.tools.mcp import normalize_mcp_content


class McpResultTests(unittest.TestCase):
    def test_text_content_is_preserved(self):
        self.assertEqual(normalize_mcp_content(SimpleNamespace(type="text", text="ok")), {
            "type": "text", "text": "ok"
        })

    def test_image_content_keeps_mime_and_base64(self):
        self.assertEqual(normalize_mcp_content(SimpleNamespace(
            type="image", mimeType="image/png", data="ZmFrZQ=="
        )), {
            "type": "image", "mime_type": "image/png", "data": "ZmFrZQ=="
        })
