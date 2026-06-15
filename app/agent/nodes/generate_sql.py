import yaml
from langchain_core.output_parsers import  StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.prompt.prompt_loader import load_prompt
from app.core.log import logger

async def generate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "生成sql", "status": "running"})
    try:
        metric_infos = state["metric_infos"]
        table_infos = state["table_infos"]
        query=state["query"]
        date_info=state["date_info"]
        db_info=state["db_info"]

        prompt = PromptTemplate(template=load_prompt("generate_sql"), input_variables=["metric_infos", "table_infos", "query", "date_info", "db_info"])
        output_parser = StrOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {"query": query,
             "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
             "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
             "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
             "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False)
             })
        logger.info(f"生成的SQL: {result}")
        writer({"type": "progress", "step": "生成sql", "status": "success"})
        return {"sql": result}
    except Exception as e:
        writer({"type": "progress", "step": "生成sql", "status": "error"})
        logger.error(f"生成SQL失败:{str(e)}")
        raise

