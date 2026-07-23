from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def load_memory(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    step = "加载记忆"
    writer({"type": "progress", "step": step, "status": "running"})
    try:
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
        memory = {
            "working": [{"role": item.role, "content": item.content} for item in messages],
            "latest_result": latest_result,
            "long_term": [
                {"type": item.memory_type, "content": item.content, "confidence": item.confidence}
                for item in long_term
            ],
        }
        writer({"type": "progress", "step": step, "status": "success"})
        logger.info(f"加载记忆成功: working={len(messages)}, long_term={len(long_term)}")
        return {"memory": memory}
    except Exception as exc:
        writer({"type": "progress", "step": step, "status": "error"})
        logger.error(f"加载记忆失败: {str(exc)}")
        raise
