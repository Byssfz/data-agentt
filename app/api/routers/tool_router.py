from fastapi import APIRouter

from app.agent.graph import tool_registry
from app.api.schemas.tool_schema import ToolCatalogItem, ToolCatalogResponse


tool_router = APIRouter()


@tool_router.get("/api/tools", response_model=ToolCatalogResponse)
async def list_tools() -> ToolCatalogResponse:
    return ToolCatalogResponse(tools=[
        ToolCatalogItem(
            name=tool.name,
            description=tool.description,
            kind=tool.kind,
            input_schema=tool.input_schema,
            read_only=tool.read_only,
            allowed_roles=sorted(tool.allowed_roles),
            allowed_intents=sorted(tool.allowed_intents),
        )
        for tool in tool_registry.list()
    ])
