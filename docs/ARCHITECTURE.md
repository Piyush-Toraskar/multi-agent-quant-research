# Architecture and code-reading guide

Read in this order: `schemas.py`, `tools/market_data.py`, `quant/backtest.py`,
`tools/registry.py`, `tools/client.py`, `agents/`, `graph/workflow.py`, `service.py`, `api/routes.py`.

## Orchestration

Both workflow implementations use the same asynchronous node functions and the same state schema:

```text
planner -> data -> quant -> risk -> critic --pass/unfixable--> report
                              ^      |
                              |   bounded revision
                              +------+
```

The revision route returns to quant, then risk and critic. Node output dictionaries merge into
shared state. LangGraph compiles the state graph and calls `ainvoke`; the native engine implements
the same bounded routing. `auto` selects LangGraph when importable and records the chosen engine.
No package installation or silent recovery from a broken LangGraph import happens at runtime.

## Agent versus tool

An agent produces a hypothesis or requests an action. A tool validates arguments and computes the
answer. In demo mode a deterministic policy performs the actions; in LLM mode tool schemas and
per-role SKILL.md content are supplied to a Chat Completions endpoint. Each role has a limited turn
budget. Explicit request parameters and approved artifact identifiers cannot be changed by the model.
The reporter uses actual tool outputs rather than free-form numeric generation.

Only read-only research operations and local persistence are exposed. The tools do not run arbitrary
SQL, shell commands or model-written Python. An unrestricted coding/sandbox agent is intentionally
outside this implementation's scope.

## MCP, not just a decorator

The application launches three child Python processes with the same `sys.executable`. Each connects
over UTF-8, newline-delimited JSON-RPC 2.0 on stdin/stdout:

```text
initialize -> negotiated protocol + tool capability
notifications/initialized
 tools/list -> JSON Schema tool definitions
 tools/call -> validated arguments -> structured/text result
stdin close -> bounded process cleanup
```

Market, quant and database tool definitions come from `app/tools/registry.py`; the schema is derived
from Pydantic models and checked again before execution. A discovered tool must also be on the local
allow-list. The client validates response IDs, applies tool timeouts, drains stderr, bounds message
sizes and cleans up processes. Only data/tool configuration is placed in the child environment;
LLM credentials are not included or loaded from `.env` by the built-in server launcher. This is not
an OS security boundary: processes still run as the same local user.

The built-in path supports the explicitly advertised MCP 2025-06-18 tools subset. The optional
low-level official SDK adapter targets MCP Python SDK 1.x and returns standard text tool results.
It is not a promise of complete MCP feature coverage or arbitrary third-party-host interoperability.

## Persistence and concurrency

SQLAlchemy models create schema v1 when the app starts. SQLite uses WAL, foreign keys and a busy
timeout. Repository queries are bound/parameterised and bounded in result size. A limited thread pool
runs research jobs; each receives its own event loop and MCP processes. On Windows a proactor loop
is used for subprocess support, independently of Uvicorn's event loop.

The database stores run status, request, result and ordered action events. Immutable JSON files store
price snapshots and full backtest artifacts, keyed by the hash of their canonical bytes. Loading a
file verifies its hash. Replay reuses the price snapshot, fixes the selected strategy and recomputes.
A new run ID, report telemetry and artifact metadata can differ even when numerical results agree.

This is one local service process, not a distributed worker design. The queue is not durable; startup
marks unfinished work interrupted. There is no claim of resumable LangGraph checkpoints. Schema v1
uses `create_all`; future schema changes require a real migration rather than pretending `create_all`
can migrate tables. SQLite is the tested database path; a PostgreSQL connection/Compose profile is supplied.

## Extending deliberately

A new strategy needs a new explicit schema enum, signal generator, methodology and causality tests.
A new data provider must preserve snapshot provenance and distinguish real data from fixtures.
A new tool needs a strict request model, registry entry, scoped role permission and tests.
Do not enable arbitrary `eval`, `exec`, shell access or unrestricted SQL to make the agent appear
more autonomous. Add authentication and proper per-user isolation before any hosted deployment.
