import asyncio
import base64
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.tools.builtin import (
    MAX_EXPORT_ROWS,
    draw_treemap,
    export_excel,
    mermaid_treemap,
    summarize_result,
)


class BuiltinToolTests(unittest.TestCase):
    def test_summary_and_treemap(self):
        rows = [{"地区": "华北", "销售额": 10}, {"地区": "华东", "销售额": 20}]
        summary = summarize_result({"rows": rows})
        self.assertIn("共 2 行", summary["text"])
        self.assertEqual(summary["numeric_totals"]["销售额"], 30)

        chart = mermaid_treemap({"rows": rows})
        self.assertTrue(chart["mermaid_code"].startswith("treemap-beta"))
        self.assertIn('"华北": 10', chart["mermaid_code"])

    def test_export_excel_creates_valid_package(self):
        result = export_excel({"rows": [{"地区": "华北", "销售额": 10}]})
        path = Path("exports") / result["filename"]
        try:
            self.assertTrue(zipfile.is_zipfile(path))
            with zipfile.ZipFile(path) as archive:
                self.assertIn("xl/workbook.xml", archive.namelist())
                self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())
        finally:
            path.unlink(missing_ok=True)

    def test_export_rejects_too_many_rows(self):
        with self.assertRaisesRegex(ValueError, "rows exceeds"):
            export_excel({"rows": [{}] * (MAX_EXPORT_ROWS + 1)})

    def test_draw_rejects_oversized_image(self):
        registry = SimpleNamespace(
            list=lambda: [SimpleNamespace(name="mermaid.validate_and_render_mermaid_diagram")],
            execute=AsyncMock(return_value={"content": [{
                "type": "image",
                "mime_type": "image/png",
                "data": base64.b64encode(b"too large").decode(),
            }]}),
        )
        with patch("app.tools.builtin.MAX_IMAGE_BASE64_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "exceeds the limit"):
                asyncio.run(draw_treemap({"rows": [{"地区": "华北", "销售额": 10}]}, registry=registry))


if __name__ == "__main__":
    unittest.main()
