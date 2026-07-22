from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.tools.builtin import EXPORT_DIR


export_router = APIRouter()


@export_router.get("/api/exports/{filename}")
async def download_export(filename: str) -> FileResponse:
    if Path(filename).name != filename or not filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Invalid export filename")
    path = EXPORT_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )
