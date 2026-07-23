from __future__ import annotations

import re
import uuid
import zipfile
import base64
import time
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


EXPORT_DIR = Path(__file__).parents[2] / "exports"
MAX_EXPORT_ROWS = 10_000
MAX_EXPORT_FILE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BASE64_BYTES = 8 * 1024 * 1024
EXPORT_RETENTION_SECONDS = 24 * 60 * 60


def _rows(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    rows = arguments.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")
    if len(rows) > MAX_EXPORT_ROWS:
        raise ValueError(f"rows exceeds the limit of {MAX_EXPORT_ROWS}")
    return [row if isinstance(row, dict) else {"value": row} for row in rows]


def _cleanup_exports() -> None:
    if not EXPORT_DIR.is_dir():
        return
    cutoff = time.time() - EXPORT_RETENTION_SECONDS
    for path in EXPORT_DIR.glob("query_result_*.xlsx"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def _cell(value: Any, row: int, column: int) -> str:
    ref = f"{chr(65 + column)}{row}"
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def _write_xlsx(path: Path, rows: list[dict[str, Any]], title: str) -> None:
    columns = list(dict.fromkeys(column for row in rows for column in row))
    if not columns:
        columns = ["result"]
    sheet_rows = [
        "<row r=\"1\">" + "".join(_cell(column, 1, index) for index, column in enumerate(columns)) + "</row>"
    ]
    for row_number, row in enumerate(rows, start=2):
        sheet_rows.append(
            f'<row r="{row_number}">' + "".join(
                _cell(row.get(column, ""), row_number, index)
                for index, column in enumerate(columns)
            ) + "</row>"
        )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(title[:31] or "Result")}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxml-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def export_excel(arguments: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(arguments)
    title = str(arguments.get("title", "Query Result"))
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_exports()
    filename = f"query_result_{uuid.uuid4().hex}.xlsx"
    path = EXPORT_DIR / filename
    _write_xlsx(path, rows, title)
    if path.stat().st_size > MAX_EXPORT_FILE_BYTES:
        path.unlink(missing_ok=True)
        raise ValueError(f"generated export exceeds the limit of {MAX_EXPORT_FILE_BYTES} bytes")
    return {
        "type": "file",
        "filename": filename,
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "download_url": f"/api/exports/{filename}",
        "row_count": len(rows),
    }


def summarize_result(arguments: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(arguments)
    if not rows:
        return {"type": "summary", "text": "查询结果为空。", "row_count": 0}
    columns = list(dict.fromkeys(column for row in rows for column in row))
    numeric_totals: dict[str, float] = {}
    for column in columns:
        values = [row.get(column) for row in rows]
        numeric = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
        if numeric:
            numeric_totals[column] = sum(numeric)
    details = [f"共 {len(rows)} 行，包含字段：{', '.join(columns)}。"]
    if numeric_totals:
        details.append("数值字段合计：" + "; ".join(f"{key}={value:g}" for key, value in numeric_totals.items()) + "。")
    return {"type": "summary", "text": "".join(details), "row_count": len(rows), "numeric_totals": numeric_totals}


def mermaid_treemap(arguments: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(arguments)
    if not rows:
        raise ValueError("无法从空结果生成树状图")
    label_column = str(arguments.get("label_column") or next(iter(rows[0])))
    value_column = str(arguments.get("value_column") or next(
        (column for column, value in rows[0].items() if isinstance(value, (int, float))),
        "",
    ))
    if not value_column:
        raise ValueError("树状图需要一个数值字段")
    safe = lambda value: re.sub(r"[\"{}]", "", str(value)).replace("\n", " ")
    lines = ['treemap-beta', '"各地区销售额"']
    for row in rows:
        lines.append(f'    "{safe(row.get(label_column, "未命名"))}": {row.get(value_column, 0)}')
    return {"mermaid_code": "\n".join(lines), "label_column": label_column, "value_column": value_column}


async def draw_treemap(arguments: dict[str, Any], *, role: str = "user", registry: Any = None) -> dict[str, Any]:
    """Build and render a treemap through the configured Mermaid MCP tool."""
    if registry is None:
        raise RuntimeError("Tool registry is required for treemap rendering")
    chart_input = mermaid_treemap(arguments)
    mcp_name = "mermaid.validate_and_render_mermaid_diagram"
    if mcp_name not in {tool.name for tool in registry.list()}:
        raise RuntimeError("Mermaid MCP 工具尚未连接，无法渲染树状图")
    rendered = await registry.execute(
        mcp_name,
        {
            "prompt": "请渲染各地区销售额树状图",
            "mermaidCode": chart_input["mermaid_code"],
            "diagramType": "treemap",
            "clientName": "data-agentt",
            "useUrlShortener": False,
        },
        role=role,
        intent="tool_call",
    )
    content = rendered.get("content", [])
    images = [item for item in content if item.get("type") == "image"]
    text = "\n".join(item.get("text", "") for item in content if item.get("type") == "text")
    preview_match = re.search(r"https://mermaid\.ai/live/edit\?[^\s)]+", text)
    if images:
        image = images[0]
        image_data = image.get("data", "")
        if not isinstance(image_data, str):
            raise ValueError("MCP image data must be base64 text")
        try:
            decoded_size = len(base64.b64decode(image_data, validate=True))
        except (ValueError, TypeError) as exc:
            raise ValueError("MCP image data is not valid base64") from exc
        if decoded_size > MAX_IMAGE_BASE64_BYTES:
            raise ValueError(f"generated image exceeds the limit of {MAX_IMAGE_BASE64_BYTES} bytes")
        return {
            "type": "image",
            "message": "树状图已生成",
            "mime_type": image.get("mime_type", "image/png"),
            "data": image_data,
            "preview_url": preview_match.group(0) if preview_match else None,
        }
    return {"type": "text", "message": "树状图生成失败", "detail": text[:500]}
