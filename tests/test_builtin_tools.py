import unittest
import zipfile
from pathlib import Path

from app.tools.builtin import export_excel, mermaid_treemap, summarize_result


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


if __name__ == "__main__":
    unittest.main()
