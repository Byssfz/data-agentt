import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.prompt.prompt_loader import load_prompt
from app.core.log import logger

async def filter_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "过滤指标", "status": "running"})
    try:
        query = state["query"]
        metric_infos=state["metric_infos"]

        prompt = PromptTemplate(template=load_prompt("filter_metric_info"), input_variables=["query", "metric_infos"])
        output_parser = JsonOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {"query": query, "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False)})

        filtered_metric_infos=[metric_info for metric_info in metric_infos if metric_info["name"] in result]
        logger.info(f"过滤后的指标: {[filtered_metric_infos['name'] for filtered_metric_infos in filtered_metric_infos]}")
        writer({"type": "progress", "step": "过滤指标", "status": "success"})
        return {"metric_infos":filtered_metric_infos}
    except Exception as e:
        writer({"type": "progress", "step": "过滤指标", "status": "error"})
        logger.error(f"过滤指标失败:{str(e)}")
        raise