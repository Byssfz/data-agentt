from typing import Any

from pydantic import BaseModel, Field


class ToolCatalogItem(BaseModel):
    name: str
    description: str
    kind: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    read_only: bool
    allowed_roles: list[str]
    allowed_intents: list[str]


class ToolCatalogResponse(BaseModel):
    tools: list[ToolCatalogItem]
