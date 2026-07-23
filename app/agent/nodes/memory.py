from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


async def load_memory(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    repository = runtime.context["memory_repository"]
    messages = await repository.list_messages(state["session_id"])
    long_term = await repository.list_long_term(state["user_id"])
    latest_result = next(
        (
            item.metadata_json.get("result")
            for item in reversed(messages)
            if item.role == "assistant" and isinstance(item.metadata_json, dict)
            and isinstance(item.metadata_json.get("result"), list)
        ),
        None,
    )
    return {
        "memory": {
            "working": [{"role": item.role, "content": item.content} for item in messages],
            "latest_result": latest_result,
            "long_term": [
                {"type": item.memory_type, "content": item.content, "confidence": item.confidence}
                for item in long_term
            ],
        }
    }
