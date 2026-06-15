from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.entities.value_info import ValueInfo
from app.prompt.prompt_loader import load_prompt
from app.core.log import logger


async def recall_value(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段取值", "status": "running"})
    try:
        query = state["query"]
        keywords = state["keywords"]
        value_es_repository=runtime.context["value_es_repository"]

        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_value_recall"), input_variables=["query"])
        output_parser = JsonOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query})
        keywords = set(result + keywords)
        values_map: dict[str, ValueInfo] = {}
        for keyword in keywords:
            values:list[ValueInfo]=await value_es_repository.search(keyword)
            for value in values:
                if value.id not in values_map:
                    values_map[value.id]=value
        retrieved_value_infos: list[ValueInfo] = list(values_map.values())
        logger.info(f"检索到字段取值信息:{values_map.keys()}")
        writer({"type": "progress", "step": "召回字段取值", "status": "success"})
        return {"retrieved_value_infos": retrieved_value_infos}
    except Exception as e:
        writer({"type": "progress", "step": "召回字段取值", "status": "error"})
        logger.error(f"召回字段取值失败:{str(e)}")
        raise
