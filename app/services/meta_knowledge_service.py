import uuid
from dataclasses import asdict
from pathlib import Path

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf

from app.conf.meta_config import MetaConfig
from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repositoriy import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.core.log import logger


class MetaKnowledgeService:
    def __init__(self,
                 meta_mysql_repository:MetaMySQLRepository,
                 dw_mysql_repository:DWMySQLRepository,
                 column_qdrant_respository:ColumnQdrantRepository,
                 embedding_client:HuggingFaceEndpointEmbeddings,
                 value_es_repository:ValueESRepository,
                 metric_qdrant_repository:MetricQdrantRepository):
        self.meta_mysql_repository:MetaMySQLRepository=meta_mysql_repository
        self.dw_mysql_repository:DWMySQLRepository=dw_mysql_repository
        self.column_qdrant_repository=column_qdrant_respository
        self.embedding_client=embedding_client
        self.value_es_respository=value_es_repository
        self.metric_qdrant_repository=metric_qdrant_repository

    async def _save_tables_to_meta_db(self,meta_config)->list[ColumnInfo]:
        table_infos:list[TableInfo]=[]
        column_infos:list[ColumnInfo]=[]

        for table in meta_config.tables:

            table_info=TableInfo(id=table.name,
                           name=table.name,
                           role=table.role,
                           description=table.description)
            table_infos.append(table_info)
            column_types:dict[str,str]= await self.dw_mysql_repository.get_column_types(table.name)
            for column in table.columns:
                column_values=await self.dw_mysql_repository.get_column_values(table.name,column.name,limit=10)
                column_info=ColumnInfo(id=f"{table.name}.{column.name}",
                                            name=column.name,
                                            type=column_types[column.name],
                                            role=column.role,
                                            examples=column_values,
                                            description=column.description,
                                            alias=column.alias,
                                            table_id=table.name
                            )
                column_infos.append(column_info)
        #transaction可以手动管理try，catch，也可以像这样，它自动提交和回滚
        async with self.meta_mysql_repository.session.begin():
            self.meta_mysql_repository.save_table_infos(table_infos)
            self.meta_mysql_repository.save_column_infos(column_infos)
        return column_infos

    async def _save_columns_to_qdrant(self,column_infos:list[ColumnInfo]):
        await self.column_qdrant_repository.ensure_collection()
        points: list[dict] = []
        for column_info in column_infos:
            points.append(
                {"id": uuid.uuid4(), "embedding_text": column_info.name, "payload": asdict(column_info)})
            points.append(
                {"id": uuid.uuid4(), "embedding_text": column_info.description, "payload": asdict(column_info)})
            for alia in column_info.alias:
                points.append(
                    {"id": uuid.uuid4(), "embedding_text": alia, "payload": asdict(column_info)})

        embedding_texts = [point["embedding_text"] for point in points]
        embedding_batch_size = 20
        embeddings: list[list[float]] = []

        for i in range(0, len(embedding_texts), embedding_batch_size):
            batch_embedding_texts = embedding_texts[i:i + embedding_batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
            # 这里用extend而不是append否则是将整个列表加入，而不是遍历列表每个元素再加入
            embeddings.extend(batch_embeddings)

        ids = [point["id"] for point in points]

        payloads = [point["payload"] for point in points]

        await self.column_qdrant_repository.upsert(ids, payloads, embeddings)

    async def _save_values_to_es(self,meta_config):
        await self.value_es_respository.ensure_index()

        value_infos: list[ValueInfo] = []

        for table in meta_config.tables:
            for column in table.columns:
                if column.sync:
                    current_column_values = await self.dw_mysql_repository.get_column_values(table.name, column.name,
                                                                                             100000)
                    current_values_infos = [
                        ValueInfo(id=f"{table.name}.{column.name}.{current_column_value}", value=current_column_value,
                                  column_id=f"{table.name}.{column.name}") for current_column_value in
                        current_column_values]
                    value_infos.extend(current_values_infos)
        await self.value_es_respository.index(value_infos)

    async def _save_metrics_to_meta(self,meta_config:MetaConfig)->list[MetricInfo]:
        metric_infos: list[MetricInfo] = []
        column_metrics: list[ColumnMetric] = []
        for metric in meta_config.metrics:
            metrice_info = MetricInfo(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            metric_infos.append(metrice_info)
            for column in metric.relevant_columns:
                column_metric = ColumnMetric(column_id=column, metric_id=metric.name)
                column_metrics.append(column_metric)

        async with self.meta_mysql_repository.session.begin():
            self.meta_mysql_repository.save_metrics_infos(metric_infos)
            self.meta_mysql_repository.save_column_metrics(column_metrics)
        return  metric_infos

    async def _save_metrics_to_qdrant(self,metric_infos:list[MetricInfo]):
        await self.metric_qdrant_repository.ensure_collection()
        points: list[dict] = []
        for metric_info in metric_infos:
            points.append(
                {"id": uuid.uuid4(), "embedding_text": metric_info.name, "payload": asdict(metric_info)})
            points.append(
                {"id": uuid.uuid4(), "embedding_text": metric_info.description, "payload": asdict(metric_info)})
            for alia in metric_info.alias:
                points.append(
                    {"id": uuid.uuid4(), "embedding_text": alia, "payload": asdict(metric_info)})

            embedding_texts = [point["embedding_text"] for point in points]
            embedding_batch_size = 20
            embeddings: list[list[float]] = []
            for i in range(0, len(embedding_texts), embedding_batch_size):
                batch_embedding_texts = embedding_texts[i:i + embedding_batch_size]
                batch_embeddings: list[list[float]] = await self.embedding_client.aembed_documents(
                    batch_embedding_texts)
                embeddings.extend(batch_embeddings)

            ids = [point["id"] for point in points]

            payloads = [point["payload"] for point in points]

            await self.metric_qdrant_repository.upsert(ids, payloads, embeddings)

    async def build(self,config_path:Path):
        # 1.加载配置文件
        #1.看"从哪个目录运行的程序"（当前工作目录 CWD）
        #2.绝对路径
        context = OmegaConf.load(config_path)
        schema = OmegaConf.structured(MetaConfig)
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))
        logger.info("加载配置文件成功")
        # 2.处理表信息
        if meta_config.tables:
            # print(meta_config.metrics)
            # 2.1 保存表信息到meta数据库
            column_infos=await self._save_tables_to_meta_db(meta_config)
            logger.info("保存表信息和字段信息到数据库成功")
            # 2.2 为字段信息建立向量索引
            await self._save_columns_to_qdrant(column_infos)
            logger.info("为字段信息建立向量索引成功")
            # 2.3 为字段取值建立全文索引
            await self._save_values_to_es(meta_config)
            logger.info("为指定的维度字段取值建立全文索引成功")


        # 3.处理指标信息
        if meta_config.metrics:
            metric_infos=await self._save_metrics_to_meta(meta_config)
            logger.info("保存指标信息到数据库成功")
            await self._save_metrics_to_qdrant(metric_infos)
            logger.info("为指标信息建立向量索引成功")



