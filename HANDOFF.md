# Handoff

## 已完成什么

- 建立统一工具注册体系：支持 Python 函数、LangGraph 子图和 MCP 工具；MCP 配置支持 stdio/SSE，并有角色、意图、只读/变更和超时控制。
- 请求支持 `user_id`、`session_id`；工作记忆保存会话对话历史，长期记忆保存偏好、事实、话术含义和长期指令。
- 主图已接入 `load_memory → intent_recognition → route_by_intent`，现有 SQL 流程作为查询子图运行。
- 意图识别已从纯字符串匹配升级为：规则评分 → 置信度门控 → 结构化大模型兜底 → 澄清节点。
- 意图事件通过 SSE 返回 `intent`、`confidence`、`source`、`reason`、候选意图和实体。
- 记忆只注入意图识别路由器，不再注入 SQL 生成 Prompt；历史查询节点可读取已加载的会话历史。
- 新增意图配置：`conf/app_config.yaml` 中可调整规则阈值、记忆轮数和结构化输出方式。
- 已补充 MySQL 记忆表、MCP 示例配置、README、AGENTS.md 和测试。

## 还剩什么

- 使用完整 `uv` 环境启动应用，验证真实 LLM 的 structured output 兼容性和 SSE 全链路。
- 为意图分类增加真实业务样本集、混淆矩阵、Top-1/Top-2 间隔和置信度校准。
- 将当前规则表、意图描述和工具白名单进一步配置化。
- 接入真正的长期记忆语义检索、记忆去重/更新和后台抽取；当前抽取器只处理明确表达。
- 使用 `langchain-mcp-adapters` 评估并替换当前自写 MCP 适配器。
- 补齐 MCP、数据库 Repository、图路由和 API 的集成测试。
- 为变更类工具增加用户确认/中断恢复流程。

## 关键文件和命令

- 意图模型与规则：[app/core/intent.py](app/core/intent.py)
- 意图节点与 LLM 兜底：[app/agent/nodes/intent.py](app/agent/nodes/intent.py)
- 主图与 SQL 子图：[app/agent/graph.py](app/agent/graph.py)
- 工具注册：[app/tools/registry.py](app/tools/registry.py)
- MCP 适配：[app/tools/mcp.py](app/tools/mcp.py)
- 记忆模型/Repository：[app/models/memory.py](app/models/memory.py)、[app/repositories/mysql/meta/memory_repository.py](app/repositories/mysql/meta/memory_repository.py)
- 配置：[conf/app_config.yaml](conf/app_config.yaml)

```bash
uv sync
docker compose -f docker/docker-compose.yaml up -d
python -m unittest discover -s tests -v
python -m compileall -q app main.py tests
uv run main.py
```

## 当前卡点 / 风险

- `.venv` 已确认包含项目依赖，配置和 LangGraph 主图可成功导入；8 项单元测试和编译检查通过。
- Docker Compose 服务已运行；MySQL 账号通过显式 TCP 连接验证成功，原失败原因是容器内 socket 连接匹配 `@localhost`。
- Docker 当前 5 个服务均为 running：MySQL 3306、Qdrant 6333/6334、Embedding 8081、Elasticsearch 9200、Kibana 5601。
- `.venv` 已通过 `uv sync` 同步完成，`mcp==1.28.1` 及其依赖已安装；stdio/SSE 客户端导入和空 MCP 配置启动检查通过。
- MCP 结果适配已支持 text、image 和 resource 内容块；图片结果保留 MIME 类型和 base64 数据，可通过 SSE `tool_result` 返回。
- MCP 配置已支持 stdio、SSE 和 Streamable HTTP，并补充绘图工具配置示例；LLM 工具调用提示会要求返回 `entities.tool_name` 和 `entities.arguments`。
- `meta` 库的 `conversation_message`、`long_term_memory` 已使用非破坏性的 `CREATE TABLE IF NOT EXISTS` 创建，并通过 SQLAlchemy/asyncmy 读取验证。
- FastAPI 已完成真实 SSE 冒烟：安全请求返回 `security / 0.97 / rule`；模糊请求进入 LLM fallback。Codex 沙箱请求 DeepSeek 受限，但用户已确认直接运行 `app.agent.llm` 正常，项目侧 LLM 配置不再视为卡点。
- 两次冒烟请求均成功写入 `conversation_message`，当前测试 session 共 4 条消息。
- Codex 沙箱访问 `https://api.deepseek.com` 会返回 `Connection error`，但用户本机运行 `app.agent.llm` 正常；真实 `function_calling` structured output 应在用户本机环境继续验证，代码保留了无 method 参数的兼容回退。
- `docker/mysql/meta.sql` 新表只会在新建 MySQL 数据卷时自动执行，已有数据卷需要手动建表。
- `user_id` 当前来自请求体，生产环境必须改为从认证中间件解析，不能信任客户端身份。
- LLM 返回的 confidence 不是天然校准概率，不能单独作为安全授权依据。
- 配置文件当前包含开发环境凭证，部署前必须迁移到环境变量或密钥管理系统。

## 下次继续的第一步

启动一个最小绘图类 stdio MCP server，验证配置加载、工具发现、角色/意图权限过滤、图片结果和实际调用；随后在用户本机验证 structured output，并测试同一 `session_id` 的追问意图是否能借助工作记忆正确路由。
