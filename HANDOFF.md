# Handoff

## 当前状态

系统已确定采用“统一 LLM 路由 + 统一 ToolRegistry 执行”的简化架构：路由节点只输出 `tool_call`、`chat` 或 `refuse`，工具调用直接携带 `tool_name + arguments`；ToolRegistry 负责校验并执行 Python 函数、LangGraph 工作流或 MCP 工具。路由上下文包含当前会话历史和用户全部长期记忆。当前开始把代码从旧的 `intent + entities` 契约收敛到该新契约。

## 已完成什么

- 统一工具注册：支持 Python 函数、LangGraph 子图和 MCP 工具。
- 工具权限：支持角色、允许意图、只读/变更标记和超时；变更工具默认拒绝。
- MCP 客户端：支持 stdio、SSE、Streamable HTTP；启动时发现工具，调用时建立连接。
- MCP 结果：支持 text、image、resource；图片保留 MIME 类型和 base64 数据，并可通过 SSE `tool_result` 返回。
- 新增 `GET /api/tools`，返回工具名称、类型、输入 schema、只读属性、角色和意图限制。
- 请求支持 `user_id`、`session_id`；工作记忆保存会话历史，长期记忆保存偏好、事实、话术含义和长期指令。
- 主图流程为 `load_memory → intent_recognition → route_by_intent`，现有 SQL 流程作为查询子图运行。
- 意图识别为规则评分 → 置信度门控 → structured LLM fallback → clarification；SSE 返回 intent、confidence、source、reason、alternatives、entities。
- 记忆只注入意图路由器；SQL Prompt 不再注入记忆。历史查询节点可读取已加载的会话历史。
- 已创建并验证 MySQL 表：`conversation_message`、`long_term_memory`。
- 已通过本地绘图 MCP fixture 的应用 lifespan 冒烟：发现 `drawing.draw_image`，调用返回 `image/png`。
- 已配置并验证官方 Mermaid Streamable HTTP MCP：发现 `mermaid.validate_and_render_mermaid_diagram`、`mermaid.get_diagram_title`、`mermaid.get_diagram_summary`。
- 已兼容 `mcp==1.28.1` 的 Streamable HTTP 三元组返回值，工具发现验证通过。
- DeepSeek 意图路由已切换为 `json_mode`，Prompt 明确要求 JSON，并保留 `function_calling → json_mode` fallback；真实模糊请求验证通过。
- SQL 子图结果已回流到主图，新增结果后处理节点，可根据原始请求自动触发摘要、Excel 导出和 Mermaid 树状图。
- 新增本地工具 `summarize_result`、`export_excel`、`draw_treemap`；Excel 通过 `/api/exports/{filename}` 下载，`draw_treemap` 内部组合 Mermaid 代码生成与 Mermaid MCP 渲染。
- 官方 Mermaid treemap 已改用 `treemap-beta` 语法；真实请求“统计各个地区的销售额并导出树状图”已返回 5 个地区结果和 PNG 图片。
- 真实组合请求“统计各个地区的销售额，并总结结果、导出 Excel 和树状图”已验证：SQL 结果、摘要、合法 XLSX 和 Mermaid PNG 均通过 SSE 返回。
- 前端已增加 `tool_result` 的摘要、文件下载和 base64 图片渲染。
- Mermaid MCP 的冗长原始文本、完整代码和提示词不再直接展示给用户；后端仅返回“树状图已生成”、图片和可选预览链接。
- `.venv` 已通过 `uv sync` 安装 `mcp==1.28.1`；当前 20 项测试全部通过，编译检查通过。
- `ToolRegistry` 已使用 JSON Schema 在注册时校验 schema、执行时校验 arguments；缺少必填参数、类型错误和额外字段会在 handler 执行前失败。
- MCP server 注册已按 server 隔离异常；单个 server 连接、初始化或工具发现失败时记录错误并继续启动其他 MCP server。
- 已删除 `post_process_result` 节点和查询完成后的自动后处理连线；查询结果通过 `conversation_message.metadata_json.result` 保存，后续独立工具调用可读取上一轮结构化结果并补齐 `rows` 参数。
- `data.query` 已从占位工具改为真正执行 SQL 子图的统一工具；`text_to_sql` 和 `schema_query` 意图现在都会进入 `tool_call`，由工具注册表调用 `data.query`。
- 意图识别已改为每轮都调用结构化 LLM；规则分类只作为 Prompt 参考，不再因规则置信度达标而跳过 LLM。LLM 统一决定意图、工具名和工具参数，服务端只补充会话身份及上一轮结果上下文。

## 本轮已确认的架构基线

- 路由输出固定为三类：`tool_call`、`chat`、`refuse`。
- `tool_call` 由 LLM 直接输出命名空间工具名和参数；服务端不再增加独立的参数规划层。
- `ToolRegistry` 在注册时准备函数、LangGraph 或 MCP 的执行适配；路由层不关心工具实现类型。
- 当前工具范围优先收敛为 `data.query`、`result.export_excel`、`chart.draw`。
- `data.query` 接收自然语言查询参数，SQL 生成、校验和执行继续由已有 LangGraph 工作流完成。
- 路由 LLM 输入当前请求、会话历史和全部长期记忆；工具结果应以会话历史中的结构化消息继续支持后续请求。
- 工具名或参数校验失败最多自动修正一次；仍失败则澄清或返回错误。
- 不支持或高风险请求由 `refuse` 分支直接结束，不进入工具执行。

## 本轮已完成

- `IntentDecision` 增加固定的 `tool_call`、`chat`、`refuse` 路由契约。
- `tool_call` 直接输出 `tool_name + arguments`，并写入主图 State 后交给 ToolRegistry。
- 主图增加独立 `refuse` 节点；聊天回复使用路由模型返回的 `answer`。
- Excel 和绘图注册为 `result.export_excel`、`chart.draw` 命名空间工具；`data.query` 继续调用已有 SQL LangGraph。
- 保持现有 ToolRegistry 的 JSON Schema、权限和 MCP 能力，不重做已经验证的底层工具链。
- 新增 chat/refuse 路由测试；`.venv` 中没有 pytest，因此使用 `unittest discover` 验证 20 项测试，并通过 compileall。
- 工具调用校验失败现在最多触发一次 LLM 参数修正；修正后的工具名和参数仍会重新经过 ToolRegistry 校验。
- `data.query` 的 `query_result.rows` 会额外以 `result` 事件发出，保证 QueryService 能保存结果供下一轮导出或绘图使用。
- 新增统一工具目录测试，确认 `data.query`、`result.export_excel`、`chart.draw` 均已注册；当前测试总数为 20 项。
- 真实 `GET /api/tools` 返回 200，命名空间工具和已发现的 Mermaid MCP 工具均可见。
- 真实 `POST /api/query` 闲聊冒烟通过：SSE 返回 `route=chat`、模型回答和 session 事件。
- 真实跨轮次 E2E 通过：同一会话先调用 `data.query` 返回 5 行地区销售数据，随后调用 `result.export_excel` 返回 XLSX 下载地址，再调用 `chart.draw` 返回 Mermaid PNG 图片。
- 记忆加载、意图识别、工具调用、闲聊、拒答、澄清、历史和权限节点现在统一输出 `progress(running/success/error)`，并使用现有 `logger` 记录节点开始、完成和失败信息。
- 前端沿用原有 steps 容器，新增意图决策、文本 result、clarification 和 history 事件展示；真实 8002 SSE 冒烟已验证“加载记忆 → 意图识别 → 闲聊回复”的完整顺序。
- 当前后端测试总数为 27 项，前端 `npm run build` 通过。
- 导出结果会清理 24 小时前的生成文件；导出最多 10,000 行、生成文件最多 10MB；MCP 图片必须是合法 base64 且解码后不超过 8MB。
- API 默认忽略客户端传入的 `user_id` 并使用 `anonymous`；仅在显式设置 `DATA_AGENT_TRUSTED_PROXY=true` 时读取可信反向代理的 `X-Authenticated-User`。

## 还剩什么

### P0：下一步优先完成

- 完善长期记忆和导出资源的用户级隔离，并补充正式认证中间件。
- 完善 MCP 启动容错：单个 MCP server 连接失败时不应阻塞整个应用启动，应记录错误并让其他工具继续可用。
- 解决真实 MCP 工具的会话复用、断线重连和健康状态；当前每次调用都会重新建立 MCP session。
- 将结果后处理从关键词触发升级为明确的结果动作意图，避免“图/导出/总结”关键词误触发。

### P1：生产化和质量

- 将 `user_id` 从请求体改为认证中间件解析，不能信任客户端身份；角色映射也应来自认证/权限系统。
- 将 `conf/app_config.yaml` 中的 API Key 迁移到环境变量或密钥管理系统。
- 为意图分类建立真实业务样本集，评估混淆矩阵、Top-1/Top-2 间隔、阈值和置信度校准。
- 为 LLM router 增加超时、重试、结构化解析错误指标和调用耗时/成本日志。
- 长期记忆增加语义检索、Embedding、去重、冲突更新、重要性衰减、删除和保留策略；当前只按用户和重要性查询。
- 将长期记忆抽取从明确正则升级为后台 LLM 抽取与合并；当前只处理“我喜欢/请记住/某话术是指”等明确表达。
- 决定历史查询是否是记忆系统的例外；当前历史节点读取已加载的工作记忆，而用户要求记忆主要服务于开头的意图识别。
- 统一 Qdrant 客户端 `1.18.0` 与服务端 `1.16.3` 版本，消除启动警告。
- 为数据库记忆表增加正式迁移流程；`docker/mysql/meta.sql` 只对新建数据卷自动执行。
- 补充真实 MCP、数据库 Repository、FastAPI、Graph 路由、权限和 SSE 图片结果集成测试。
- 评估对图片结果使用对象存储 URL，进一步避免 base64 图片直接塞进 SSE。
- 为 `export_excel` 增加正式工作簿格式、列宽/数字格式和导出保留策略；当前是最小可用 XLSX 生成器。
- 评估用官方 `langchain-mcp-adapters` 替换当前自写 MCP 适配层。

### P2：后续体验和扩展

- 为变更类工具增加用户确认、`interrupt()` 和恢复流程。
- 为工具注册增加 namespace/version/健康状态，处理多 MCP server 同名工具和重复注册。
- 前端接入 `GET /api/tools`，渲染 `tool_result` 中的 image/resource 内容（图片、摘要、Excel 已完成；resource 仍待补充）。
- 前端工具结果已完成 Mermaid 图片、简短状态、预览链接和 Excel 下载渲染；MCP resource 仍待补充。
- 增加工具调用审计日志、敏感参数脱敏和 MCP server 访问白名单/SSRF 防护。
- 将规则表、意图描述和工具白名单从 Python 代码进一步配置化。

## 关键文件

- 意图规则：[app/core/intent.py](app/core/intent.py)
- 意图与 LLM fallback：[app/agent/nodes/intent.py](app/agent/nodes/intent.py)
- 主图/SQL 子图：[app/agent/graph.py](app/agent/graph.py)
- 结果工具：[app/tools/builtin.py](app/tools/builtin.py)
- 工具注册与权限：[app/tools/registry.py](app/tools/registry.py)
- 本地结果工具：[app/tools/builtin.py](app/tools/builtin.py)
- MCP 适配：[app/tools/mcp.py](app/tools/mcp.py)
- 工具目录 API：[app/api/routers/tool_router.py](app/api/routers/tool_router.py)
- Excel 下载 API：[app/api/routers/export_router.py](app/api/routers/export_router.py)
- 记忆模型：[app/models/memory.py](app/models/memory.py)
- 记忆 Repository：[app/repositories/mysql/meta/memory_repository.py](app/repositories/mysql/meta/memory_repository.py)
- 配置：[conf/app_config.yaml](conf/app_config.yaml)
- MCP 示例：[conf/mcp_servers.example.yaml](conf/mcp_servers.example.yaml)
- 绘图 fixture：[tests/fixtures/drawing_mcp_server.py](tests/fixtures/drawing_mcp_server.py)
- 前端工具结果渲染：[data-agent-fronted/data-agent-fronted/src/App.vue](data-agent-fronted/data-agent-fronted/src/App.vue)

## 关键命令

```powershell
uv sync
docker compose -f docker/docker-compose.yaml up -d
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q app main.py tests
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

验证工具目录：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/tools
```

真实 Mermaid MCP 已验证；fixture 仍用于离线图片结果测试。真实 MCP 配置示例见 `conf/mcp_servers.example.yaml`。

## 当前卡点 / 风险

- Codex 沙箱访问 DeepSeek 可能出现 `Connection error`；用户已确认本机直接运行 `app.agent.llm` 正常。
- LLM 返回的 confidence 不是天然校准概率，不能单独作为安全授权依据。
- `user_id` 当前由请求体提供，生产环境存在身份伪造风险。
- 配置文件含开发环境凭证，存在密钥泄露风险。
- Qdrant 客户端/服务端版本不一致但目前可用。
- MCP server 默认在应用启动时连接；如果真实服务不可达，需先完成启动容错。
- MCP 图片结果使用 base64 传输，大图可能造成响应膨胀。
- 前端 Vite 构建检查受当前环境的路径访问错误影响，后端工具链和 XLSX 结构验证已通过。
- 修改前端后需要重启 Vite 开发服务，浏览器才会加载新的工具结果渲染逻辑。

## 下次继续的第一步

下一步继续补充数据查询、工具调用和拒答分支的真实前端进度验收，并处理 8000 旧后端进程无法回收的问题。
