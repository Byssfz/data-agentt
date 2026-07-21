# Data-Agentt

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2+-green.svg)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

基于 **LangGraph** 构建的智能 NL-to-SQL 数据查询代理，支持用户通过自然语言查询结构化数据库。项目结合 **RAG（检索增强生成）** 技术，利用向量检索、全文搜索和 LLM 能力，将中文自然语言问题自动转换为 SQL 并在数据仓库中执行。

## 🏗️ 架构概览

```
用户自然语言查询
       │
       ▼
┌─────────────────────────────────────────────┐
│              FastAPI 服务层                   │
│         POST /api/query (SSE 流式)           │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│           LangGraph 工作流引擎                │
│                                              │
│  抽取关键词 ─┬─→ 召回列 (Qdrant向量检索)      │
│  (jieba)    ├─→ 召回值 (ES全文检索)           │
│             └─→ 召回指标 (Qdrant向量检索)      │
│                    │                         │
│             合并检索信息                       │
│                    │                         │
│         ├─→ 过滤指标 (LLM)                    │
│         └─→ 过滤表 (LLM)                      │
│                    │                         │
│             添加额外上下文                      │
│                    │                         │
│             生成 SQL (LLM)                    │
│                    │                         │
│             校验 SQL ──→ 修正 SQL (失败时)     │
│                    │                         │
│             执行 SQL → 返回结果                │
└─────────────────────────────────────────────┘
```

## 🔧 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| **Web 框架** | FastAPI | 提供 REST API，支持 SSE 流式响应 |
| **工作流引擎** | LangGraph | 编排多节点 AI Agent 工作流 |
| **LLM** | LangChain + OpenAI 兼容 API | SQL 生成、信息过滤、SQL 修正 |
| **中文分词** | jieba | 自然语言查询关键词提取 |
| **向量数据库** | Qdrant | 列信息 & 指标信息的语义向量检索 |
| **全文检索** | Elasticsearch | 维度值的模糊匹配与检索 |
| **关系数据库** | MySQL 8.0 | 元数据存储 (meta) + 数据仓库 (dw) |
| **Embedding** | HuggingFace TEI (bge-large-zh-v1.5) | 中文文本向量化 |
| **容器化** | Docker Compose | 一键启动所有基础设施服务 |
| **包管理** | uv | Python 依赖管理 |

## 📁 项目结构

```
data-agentt/
├── main.py                    # FastAPI 应用入口
├── pyproject.toml             # 项目依赖配置
├── docker-compose.yaml        # 基础设施 Docker 编排
├── conf/
│   ├── app_config.yaml        # 应用配置（数据库、Qdrant、ES、LLM）
│   └── meta_config.yaml       # 元数据配置（表结构、指标定义、别名）
├── app/
│   ├── agent/                 # LangGraph Agent 核心
│   │   ├── graph.py           # 工作流图定义与编排
│   │   ├── state.py           # Agent 状态定义
│   │   ├── context.py         # Agent 上下文（持有各 Repository）
│   │   └── nodes/             # 工作流各节点实现
│   │       ├── extract_keywords.py    # jieba 关键词提取
│   │       ├── recall_column.py       # Qdrant 列向量召回
│   │       ├── recall_value.py        # ES 值检索召回
│   │       ├── recall_metric.py       # Qdrant 指标向量召回
│   │       ├── merge_retrieved_info.py # 合并检索结果
│   │       ├── filter_metric.py       # LLM 过滤不相关指标
│   │       ├── filter_table.py        # LLM 过滤不相关表
│   │       ├── add_extra_context.py   # 添加日期等额外上下文
│   │       ├── generate_sql.py        # LLM 生成 SQL
│   │       ├── validate_sql.py        # SQL 语法校验
│   │       ├── correct_sql.py         # LLM 修正错误 SQL
│   │       └── run_sql.py             # 执行 SQL 并返回结果
│   ├── api/                   # FastAPI 接口层
│   │   ├── routers/           # 路由定义
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── dependencies.py    # 依赖注入
│   │   └── lifespan.py        # 应用生命周期管理
│   ├── services/              # 业务服务层
│   │   ├── query_service.py   # 查询服务（编排 Agent 执行）
│   │   └── meta_knowledge_service.py  # 元知识构建服务
│   ├── repositories/          # 数据访问层
│   │   ├── mysql/             # MySQL 仓库（meta 元数据 + dw 数据仓库）
│   │   ├── qdrant/            # Qdrant 向量仓库（列 & 指标）
│   │   └── es/                # ES 仓库（维度值检索）
│   ├── clients/               # 数据库客户端管理器
│   ├── models/                # SQLAlchemy ORM 模型
│   ├── entities/              # 领域实体定义
│   ├── prompt/                # Prompt 模板加载器
│   └── scripts/               # 知识库构建脚本
├── prompts/                   # LLM Prompt 模板文件
│   ├── generate_sql.prompt
│   ├── correct_sql.prompt
│   ├── filter_metric_info.prompt
│   ├── filter_table_info.prompt
│   └── ...
└── docker/                    # Docker 相关配置
    ├── docker-compose.yaml
    ├── elasticsearch/         # ES 自定义镜像（含中文分词插件）
    ├── embedding/             # bge-large-zh-v1.5 模型文件
    └── mysql/                 # MySQL 初始化 SQL 脚本
```

## 🚀 快速开始

### 前置要求

- Python 3.13+
- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) 包管理器

### 1. 克隆项目

```bash
git clone https://github.com/your-username/data-agentt.git
cd data-agentt
```

### 2. 启动基础设施服务

```bash
docker compose -f docker/docker-compose.yaml up -d
```

该命令会启动以下服务：
- **MySQL 8.0** — 端口 3306
- **Elasticsearch** — 端口 9200（含 IK 中文分词器）
- **Kibana** — 端口 5601
- **Qdrant** — 端口 6333 (HTTP) / 6334 (gRPC)
- **HuggingFace TEI** — 端口 8081（embedding 服务）

### 3. 安装 Python 依赖

```bash
uv sync
```

### 4. 修改配置

编辑 `conf/app_config.yaml`，确保各项连接地址与你的环境一致：

```yaml
llm:
  model_name: your-model-name
  api_key: your-api-key
  base_url: your-api-base-url

db_meta:
  host: localhost
  port: 3306
  # ...
```

### 5. 构建元知识库

首次运行前，需要将 `conf/meta_config.yaml` 中定义的表结构和指标信息同步到 Qdrant 和 MySQL 中：

```bash
python -m app.scripts.build_meta_knowledge
```

### 6. 启动应用

```bash
uv run main.py
```

服务默认运行在 `http://localhost:8000`。

### 7. 测试查询

```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "统计华北地区的销售总额"}'
```

响应为 SSE（Server-Sent Events）流式数据，包含各阶段的处理进度和最终查询结果。

## 🔄 工作流详解

| 步骤 | 节点 | 描述 |
|------|------|------|
| 1 | `extract_keywords` | 使用 **jieba** 对查询进行分词，提取名词、动词、英文等关键词 |
| 2 | `recall_column` | 基于关键词在 **Qdrant** 中向量检索相关列信息 |
| 3 | `recall_value` | 基于关键词在 **Elasticsearch** 中全文检索维度值 |
| 4 | `recall_metric` | 基于关键词在 **Qdrant** 中向量检索相关指标定义 |
| 5 | `merge_retrieved_info` | 合并步骤 2-4 的检索结果 |
| 6 | `filter_metric` | **LLM** 过滤掉与查询不相关的指标 |
| 7 | `filter_table` | **LLM** 过滤掉与查询不相关的表和列 |
| 8 | `add_extra_context` | 添加当前日期等额外上下文信息 |
| 9 | `generate_sql` | **LLM** 根据过滤后的表结构、指标和上下文生成 SQL |
| 10 | `validate_sql` | 校验 SQL 语法正确性 |
| 11 | `correct_sql` | 如果校验失败，**LLM** 根据错误信息修正 SQL |
| 12 | `run_sql` | 在数据仓库 (dw) 中执行 SQL，返回查询结果 |

## 📊 示例场景

基于配置的电商数据模型（地区、客户、商品、时间维度表 + 订单事实表），支持以下典型查询：

- "统计华北地区的销售总额" → 自动关联 `dim_region` + `fact_order`，聚合 `order_amount`
- "查询2024年每个月的GMV" → 自动关联 `dim_date` + `fact_order`，按月份分组求和
- "男性客户购买最多的商品品类是什么" → 关联 `dim_customer` + `dim_product` + `fact_order`
- "计算华东地区的AOV" → 自动识别 AOV 指标定义，关联 `dim_region` 过滤

## ⚙️ 配置说明

### LLM 配置 (`conf/app_config.yaml`)

支持任何兼容 OpenAI API 格式的 LLM 服务：

```yaml
llm:
  model_name: your-model-name
  api_key: your-api-key
  base_url: https://your-api-endpoint/v1
```

### 元数据配置 (`conf/meta_config.yaml`)

定义数据仓库的表结构、列信息和业务指标：

- **tables**: 维度表 (dim) 和事实表 (fact) 的定义，包括列名、角色、描述、别名
- **metrics**: 业务指标定义（如 GMV、AOV），指定相关列和别名

别名 (alias) 用于提升向量检索的召回率，建议为每个列/指标配置丰富的同义词。

## 📝 License

MIT License

---

**注意**: 配置文件中的 API Key 等敏感信息仅为开发测试用途，请勿将真实凭证提交到公开仓库。

## 🧰 工具与记忆系统

查询接口支持通过 `user_id` 关联用户长期记忆，通过 `session_id` 复用当前会话的对话历史。首次请求可以省略 `session_id`，服务端会返回新的会话编号：

```json
{
  "user_id": "alice",
  "session_id": "session-001",
  "query": "统计本月销售总额"
}
```

系统会在请求开始时加载会话历史和用户长期记忆，并只注入意图识别路由器。规则分类置信度低于阈值时，会调用结构化大模型进行兜底判断；仍无法判断则要求用户澄清。包含“我喜欢”“我偏好”“请记住”“某话术是指”等明确表达时，会异步沉淀为偏好、指令或话术含义记忆。

工具注册入口为 `app/tools/registry.py`，函数和 LangGraph 子图通过 Python 注册；MCP 服务配置位于 `conf/app_config.yaml` 的 `mcp.servers`，stdio/SSE 示例见 `conf/mcp_servers.example.yaml`。工具默认只允许只读调用，变更工具必须显式扩展确认策略。
