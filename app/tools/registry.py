from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


ToolCallable = Callable


@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: ToolCallable | None = None
    input_schema: dict[str, Any] = field(default_factory=dict)
    read_only: bool = True
    allowed_roles: set[str] = field(default_factory=lambda: {"user", "admin"})
    allowed_intents: set[str] = field(default_factory=set)
    timeout_seconds: float = 60.0
    kind: str = "function"
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> ToolDefinition:
        if not tool.name or tool.name in self._tools:
            raise ValueError(f"Tool already registered or unnamed: {tool.name!r}")
        self._tools[tool.name] = tool
        return tool

    def register_function(self, *, name: str, description: str, **kwargs: Any):
        def decorator(fn: ToolCallable) -> ToolCallable:
            self.register(ToolDefinition(name=name, description=description, handler=fn, **kwargs))
            return fn

        return decorator

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def list(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    async def execute(self, name: str, arguments: dict[str, Any], *, role: str, intent: str) -> Any:
        tool = self.get(name)
        if role not in tool.allowed_roles:
            raise PermissionError(f"Role {role!r} cannot use tool {name!r}")
        if tool.allowed_intents and intent not in tool.allowed_intents:
            raise PermissionError(f"Intent {intent!r} cannot use tool {name!r}")
        if not tool.read_only:
            raise PermissionError(f"Mutating tool {name!r} requires explicit confirmation")
        if tool.handler is None:
            raise RuntimeError(f"Tool {name!r} has no handler")
        result = tool.handler(arguments)
        if inspect.isawaitable(result):
            return await asyncio.wait_for(result, timeout=tool.timeout_seconds)
        return result


def register_graph_tool(registry: ToolRegistry, *, name: str, description: str, graph: Any, **kwargs: Any) -> None:
    async def invoke(arguments: dict[str, Any]) -> Any:
        return await graph.ainvoke(arguments)

    registry.register(ToolDefinition(name=name, description=description, handler=invoke, kind="graph", **kwargs))
