import json
import uuid

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph, tool_registry
from app.agent.state import DataAgentState
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repositoriy import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.repositories.mysql.meta.memory_repository import MemoryRepository
from app.conf.app_config import app_config
from app.memory import extract_long_term_memories


class QueryService:
    def __init__(self,meta_mysql_repository:MetaMySQLRepository,
                 colunmn_qdrant_repository:ColumnQdrantRepository,
                 metric_qdrant_repository:MetricQdrantRepository,
                 value_es_reporitory:ValueESRepository,
                 dw_mysql_repository:DWMySQLRepository,
                 embedding_client:HuggingFaceEndpointEmbeddings,
                 memory_repository: MemoryRepository
                 ):
        self.meta_mysql_repository = meta_mysql_repository
        self.colunmn_qdrant_repository =colunmn_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_reporitory = value_es_reporitory
        self.dw_mysql_repository =dw_mysql_repository
        self.embedding_client=embedding_client
        self.memory_repository = memory_repository

    async def query(self, query: str, *, user_id: str = "anonymous", session_id: str | None = None):
        session_id = session_id or str(uuid.uuid4())
        role = app_config.roles.get(user_id, "user")
        state = DataAgentState(query=query, user_id=user_id, session_id=session_id, role=role)
        context = DataAgentContext(column_qdrrant_repository=self.colunmn_qdrant_repository,
                                   metric_qdrant_repository=self.metric_qdrant_repository,
                                   value_es_repository=self.value_es_reporitory,
                                   meta_mysql_repository=self.meta_mysql_repository,
                                   embedding_client=self.embedding_client,
                                   dw_mysql_repository=self.dw_mysql_repository,
                                   memory_repository=self.memory_repository,
                                   tool_registry=tool_registry,
                                   )
        chunks = []
        try:
            async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                chunks.append(chunk)
                yield f"data: {json.dumps(chunk, ensure_ascii=False,default=str)}\n\n"
            intent = next((item.get("intent", "unknown") for item in chunks if item.get("type") == "intent"), "unknown")
            summary = next((item.get("data", "") for item in reversed(chunks) if item.get("type") == "result"), "")
            await self.memory_repository.save_turn(
                user_id=user_id, session_id=session_id, query=query, intent=intent, response=str(summary)
            )
            for memory in extract_long_term_memories(query):
                await self.memory_repository.remember_preference(
                    user_id=user_id,
                    memory_type=memory["memory_type"],
                    content=memory["content"],
                )
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            error={"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error, ensure_ascii=False,default=str)}\n\n"
