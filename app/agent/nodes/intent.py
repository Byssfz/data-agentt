from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState


def classify_intent(query: str) -> str:
    if any(word in query for word in ("权限", "安全", "能不能访问", "允许")):
        return "security"
    if any(word in query for word in ("历史", "之前问过", "上次", "记录")):
        return "history_query"
    if any(word in query for word in ("表结构", "有哪些表", "字段", "列信息")):
        return "schema_query"
    if any(word in query for word in ("统计", "查询", "多少", "总额", "销售", "数量")):
        return "text_to_sql"
    return "chat"


async def intent_recognition(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    intent = classify_intent(state["query"])
    runtime.stream_writer({"type": "intent", "intent": intent})
    return {"intent": intent}


async def unsupported_intent(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = f"当前暂不支持意图：{state['intent']}"
    runtime.stream_writer({"type": "result", "data": message})
    return {"response": message}


async def chat_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = "你好，我可以帮助你查询数据、查看历史会话或解释当前支持的功能。"
    runtime.stream_writer({"type": "result", "data": message})
    return {"response": message}


async def history_query_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    history = state.get("memory", {}).get("working", [])
    message = {"type": "history", "data": history}
    runtime.stream_writer(message)
    return {"response": str(history)}


async def security_node(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    message = f"当前会话角色为 {state.get('role', 'user')}，工具权限由服务端配置控制。"
    runtime.stream_writer({"type": "result", "data": message})
    return {"response": message}
