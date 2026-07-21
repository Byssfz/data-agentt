from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


async def load_memory(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    repository = runtime.context["memory_repository"]
    messages = await repository.list_messages(state["session_id"])
    long_term = await repository.list_long_term(state["user_id"])
    return {
        "memory": {
            "working": [{"role": item.role, "content": item.content} for item in messages],
            "long_term": [
                {"type": item.memory_type, "content": item.content, "confidence": item.confidence}
                for item in long_term
            ],
        }
    }
