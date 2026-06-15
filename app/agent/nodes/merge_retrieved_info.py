from typing import TypedDict

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState, ColumnInfoState, MetricInfoState
from app.entities.column_info import ColumnInfo
from app.entities.table_info import TableInfo
from app.core.log import logger


async def merge_retrieved_info(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "合并召回信息", "status": "running"})
    try:
        retrieved_column_infos=state["retrieved_column_infos"]
        retrieved_metric_infos=state["retrieved_metric_infos"]
        retrieved_value_infos=state["retrieved_value_infos"]
        meta_mysql_repository=runtime.context["meta_mysql_repository"]
        #处理表信息

        # 将指标信息的相关字段信息添加到字段信息中
        retrieved_column_info_maps:dict[str,ColumnInfo]={retrieved_column_info.id: retrieved_column_info for retrieved_column_info in retrieved_column_infos}
        for retrieved_metric_info in retrieved_metric_infos:
            for relevant_column in retrieved_metric_info.relevant_columns:
               if relevant_column not in retrieved_column_info_maps:
                   column_info:ColumnInfo=await meta_mysql_repository.get_column_info_by_id(relevant_column)
                   retrieved_column_info_maps[relevant_column]=column_info

        #将字段取值加到其所属字段的examples中
        for retrieved_value_info in retrieved_value_infos:
            value=retrieved_value_info.value
            column_id=retrieved_value_info.column_id

            if column_id not in retrieved_column_info_maps:
                column_info: ColumnInfo = await meta_mysql_repository.get_column_info_by_id(column_id)
                retrieved_column_info_maps[column_id]=column_info
            if value not in retrieved_column_info_maps[column_id].examples:
                retrieved_column_info_maps[column_id].examples.append(value)


        #按照表对字段信息进行分组，整理成目标格式

        table_to_column_map:dict[str,list[ColumnInfo]]={}
        for column_info in retrieved_column_info_maps.values():
            table_id=column_info.table_id
            if table_id not in table_to_column_map:
                table_to_column_map[table_id]=[]
            table_to_column_map[table_id].append(column_info)

        #添加主键字段
        for table_id in table_to_column_map.keys():
            key_columns:list[ColumnInfo]=await meta_mysql_repository.get_key_columns_by_table_id(table_id)
            column_ids=[column_info.id for column_info in table_to_column_map[table_id]]
            for key_column in key_columns:
                if key_column.id not in column_ids:
                    table_to_column_map[table_id].append(key_column)

        table_infos: list[TableInfoState] = []
        for table_id,column_infos in table_to_column_map.items():
            columns=[ColumnInfoState(name=column_info.name,
                             type=column_info.type,
                             role=column_info.role,
                             examples=column_info.examples,
                             description=column_info.description,
                             alias=column_info.alias) for column_info in column_infos]

            table_info:TableInfo=await meta_mysql_repository.get_table_info_by_id(table_id)

            table_info_state=TableInfoState(name=table_info.name,role=table_info.role,description=table_info.description,columns=columns)

            table_infos.append(table_info_state)


        #处理指标信息
        metric_infos:list[MetricInfoState]=[MetricInfoState(name=retrieved_metric_info.name,
                                                            description=retrieved_metric_info.description,
                                                            relevant_columns=retrieved_metric_info.relevant_columns,
                                                            alias=retrieved_metric_info.alias) for retrieved_metric_info in retrieved_metric_infos]

        writer({"type": "progress", "step": "合并召回信息", "status": "success"})
        logger.info(
            f"合并召回信息: 表信息-{[table_info['name'] for table_info in table_infos]},指标信息-{[metric_info['name'] for metric_info in metric_infos]}")
        return {"table_infos":table_infos,"metric_infos":metric_infos}
    except Exception as e:
        writer({"type": "progress", "step": "合并召回信息", "status": "error"})
        logger.error(f"合并召回信息失败:{str(e)}")
        raise