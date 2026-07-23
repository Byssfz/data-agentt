import os
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.api.schemas.query_schema import QuerySchema
from app.services.query_service import QueryService

query_router=APIRouter()


def _request_user_id(request: Request, requested_user_id: str) -> str:
    """Use a proxy-authenticated identity only when explicitly enabled."""
    trusted_proxy = os.getenv("DATA_AGENT_TRUSTED_PROXY", "").lower() in {"1", "true", "yes"}
    if not trusted_proxy:
        return "anonymous"
    return request.headers.get("X-Authenticated-User") or requested_user_id or "anonymous"


@query_router.post("/api/query")
async def query(request: Request, query:QuerySchema,
                query_service:Annotated[QueryService, Depends(get_query_service)]):
    return StreamingResponse(
        query_service.query(
            query.query,
            user_id=_request_user_id(request, query.user_id),
            session_id=query.session_id,
        ),
        media_type="text/event-stream"
    )
