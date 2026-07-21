from typing import Any, TypedDict

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo

class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]


class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


class MetricInfoState(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]

class DateInfoState(TypedDict):
    date: str
    weekday: str
    quarter: str


class DBInfoState(TypedDict):
    dialect: str
    version: str


class DataAgentState(TypedDict, total=False):
    query: str
    user_id: str
    session_id: str
    role: str
    error: str | None
    intent: str
    intent_confidence: float
    intent_source: str
    intent_reason: str
    intent_alternatives: list[dict[str, Any]]
    intent_entities: dict[str, Any]
    memory: dict[str, Any]
    keywords: list[str]
    retrieved_column_infos: list[ColumnInfo]
    retrieved_metric_infos: list[MetricInfo]
    retrieved_value_infos: list[ValueInfo]
    table_infos: list[TableInfoState]
    metric_infos: list[MetricInfoState]
    date_info: DateInfoState
    db_info: DBInfoState
    sql: str
    result: Any
    response: str
