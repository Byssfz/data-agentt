# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Python 3.13+ FastAPI data-query agent. `main.py` is the application entry point. Runtime code lives in `app/`, organized by responsibility:

- `app/api/`: routers, request schemas, dependencies, and application lifespan.
- `app/agent/`: LangGraph state, workflow graph, and SQL-generation/retrieval nodes.
- `app/clients/` and `app/repositories/`: external service clients and persistence/search adapters.
- `app/entities/` and `app/models/`: domain objects and MySQL models/mappers.
- `app/services/`: application-level orchestration.
- `app/scripts/`: maintenance/bootstrap scripts such as metadata indexing.

Prompt templates are in `prompts/`; YAML configuration is in `conf/`; Docker Compose, database schemas, and local model assets are in `docker/`. Logs are generated under `logs/` and should not be committed.

## Build, Test, and Development Commands

Install locked dependencies with `uv sync`. Start required infrastructure from the repository root:

```bash
docker compose -f docker/docker-compose.yaml up -d
uv run python -m app.scripts.build_meta_knowledge
uv run main.py
```

The service listens on port 8000 by default; the README’s `curl` example exercises `POST /api/query`. Stop infrastructure with `docker compose -f docker/docker-compose.yaml down`.

## Coding Style & Naming Conventions

Use four spaces, UTF-8 source files, and PEP 8-compatible Python. Use `snake_case` for modules, functions, variables, and configuration keys; `PascalCase` for classes and Pydantic/SQLAlchemy models; and `UPPER_SNAKE_CASE` for constants. Keep API schemas at the boundary, place workflow behavior in agent nodes, and avoid embedding credentials or environment-specific values in source.

## Testing Guidelines

No test suite or test runner is currently configured. For changes, at minimum run `uv run python -m compileall app main.py` and manually exercise the affected API or script against local Docker services. Add new tests under `tests/` using `pytest` when introducing non-trivial logic; name files `test_*.py` and test functions `test_*`.

## Commit & Pull Request Guidelines

Existing commits are short and descriptive, including Chinese messages. Keep commits focused and imperative where practical (for example, `修复 SQL 校验节点`). Pull requests should explain the behavior change, list configuration or schema impacts, include validation commands/results, and attach API screenshots or request/response examples when the endpoint behavior changes. Call out required Docker services and migration steps explicitly.

## Security & Configuration Tips

Review `conf/app_config.yaml` and `conf/meta_config.yaml` before running locally. Keep secrets in ignored `.env` or local configuration, never in commits. Treat generated SQL and database credentials as sensitive, and verify Docker-exposed ports before sharing a development environment.

## Current Routing Architecture

The application uses one structured LLM routing node. Its output is a discriminated route:

- `tool_call`: includes `tool_name` and structured `arguments`.
- `chat`: includes the direct answer for the conversation model path.
- `refuse`: includes the refusal answer; no tool may execute.

The router receives the current input, conversation history, and the user's long-term memory. It may select only registered, namespaced tools. `ToolRegistry` validates the selected tool, role/intent policy, and JSON Schema arguments before execution. A registered tool may be a Python function, a LangGraph workflow, or an MCP adapter; the router does not depend on the implementation type. The initial supported tools are `data.query`, `result.export_excel`, and `chart.draw` (with compatibility aliases allowed only while existing callers are migrated).

Keep the first implementation intentionally small: tool registration owns the argument-to-handler/workflow adaptation, `data.query` owns the SQL LangGraph workflow, and the router owns route selection and argument generation. On tool-name or argument validation failure, allow at most one structured correction attempt, then return clarification or an error. Unsupported or high-risk requests are handled as `refuse` before execution.
