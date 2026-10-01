# Multi-Agent Quant Research Platform

An end-to-end, local research workbench: plan an experiment, retrieve prices, compute analytics,
backtest an approved strategy, measure risk, verify the result and export an auditable report.

**Start without an API key.** The default is a complete **synthetic-data demo** with deterministic
role policies. It uses real subprocess MCP messages, not a pretend MCP wrapper. Model-driven agents
are an explicit, separately configured mode. This is educational research software, not a trading system.

## 1. Start on your Windows machine

Extract this folder into your existing project directory. The resulting layout must have
`app`, `scripts`, `README.md` and `requirements-core.txt` directly inside:

```text
C:\Users\Piyush\OneDrive\Desktop\TowerResearch\multi-agent-quant-research
```

Do not accidentally create a second `multi-agent-quant-research` directory inside it.
Open PowerShell in the folder containing this README. Use the Python interpreter in which you
already installed the dependencies:

```powershell
python --version
python -m scripts.doctor
python -m app
```

Open **http://127.0.0.1:8000** in your browser and select **Run research**. Keep the terminal open.
Stop with **Ctrl+C**. Use `python -m app --port 8001` when port 8000 is occupied.

The doctor **does not install, reinstall or upgrade anything** without `--install`.
If it identifies missing/incompatible core packages, review the output, then run:

```powershell
python -m scripts.doctor --install
```

Only unsatisfied requirements are sent to pip; dependency resolution can still adjust transitive
packages. An isolated virtual environment is safer when sharing Python with other projects.
Python **3.11+** is required. This delivered build was tested on Linux/Python 3.13.5; Windows
launchers and Windows-specific event-loop handling are included, but were not executed on Windows here.

No Node.js, npm, GPU, Redis, PostgreSQL server or Docker is necessary for the default application.
Existing unused dependencies can remain installed. No dependency binaries or virtual environment
are bundled in the ZIP.

### Run the same complete pipeline without a browser

```powershell
python -m scripts.demo
```

This starts the tool subprocesses, executes the experiment, stores it in SQL and writes
`data/runtime/demo_report.md`. The run appears in the web application's history on the next refresh.

**Do not run individual files by filesystem path** such as `python app/tools/market_data.py`.
Run modules from the project root using `python -m ...` so package imports work correctly.

## 2. What is implemented

| Component | Working functionality |
|---|---|
| Planner | Selects a supported strategy and hypothesis; checks previous SQL research history |
| Data agent | Fetches and validates an immutable, content-addressed dataset |
| Quant agent | Asset comparisons, daily returns, beta, correlations, trailing momentum, backtesting |
| Risk agent | Historical VaR/CVaR, exposure, concentration, worst days and a labelled shock scenario |
| Critic agent | Deterministic validity checks; bounded revision route; rejects unresolved failures |
| Report stage | Renders actual tool metrics and provenance without letting an LLM invent numbers |
| Orchestration | LangGraph when installed; separately labelled native state machine otherwise |
| MCP | Three subprocess servers; initialisation, discovery, validated tool calling and cleanup |
| Storage | SQLAlchemy + SQLite by default; optional PostgreSQL configuration |
| Interface | Offline browser dashboard, equity chart, numeric correlations, action log and history |
| Exports | Markdown report, full JSON, daily equity CSV, trade CSV and exact data snapshot |
| Reproducibility | Replay the stored snapshot and chosen strategy without downloading new prices |
| Evaluation | Unit, contract, API and subprocess integration tests; 12 fixed research cases |

The three strategies are positive trailing momentum, a fast/slow SMA crossover and buy-and-hold.
Momentum and SMA invest a fixed `1 / number_of_assets` allocation in each active asset; inactive
allocations stay in cash. Buy-and-hold enters once and does not rebalance. All are long-only.

## 3. Four independent choices, not one misleading “AI mode”

| Setting | Default | Meaning |
|---|---|---|
| `AGENT_MODE` | `demo` | Deterministic role policies; **no LLM inference** |
| `WORKFLOW_ENGINE` | `auto` | Uses LangGraph if importable, otherwise explicitly labels `native` |
| `TOOL_TRANSPORT` | `mcp` | Actual JSON-RPC stdio subprocess calls |
| `MCP_IMPLEMENTATION` | `builtin` | Bundled, scoped MCP 2025-06-18 tools implementation |
| Data provider in the form | `demo` | Deterministic synthetic prices, **not market history** |

`AGENT_MODE=llm` makes the planner and four specialist agents call a configured language model.
The numerical tools and report remain deterministic. A model must issue the approved tool calls;
the application checks every argument against the experiment. Models cannot silently change the
provider, tickers, date range, costs or strategy parameters. Action summaries are recorded; private
chain-of-thought is not requested or displayed.

The built-in MCP implementation implements only the advertised local tools capabilities. It does
not implement every optional MCP feature, remote authentication, resources, prompts or sampling,
and has not been certified against third-party hosts. An **official SDK v1 adapter** is also supplied.
Neither the default demo nor the built-in MCP implementation should be described as live LLM execution.

## 4. Enable model-driven agents

Copy `.env.example` to `.env` without overwriting an existing secrets file:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit these entries in `.env`:

```dotenv
AGENT_MODE=llm
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=REPLACE_WITH_A_MODEL_AVAILABLE_TO_YOUR_ACCOUNT
LLM_API_KEY=REPLACE_WITH_YOUR_KEY
```

Restart the application. The endpoint/model must support the standard **Chat Completions function-tool
API**, including `tool_choice`. A compatible local or third-party endpoint can be configured, but this
project does not claim universal provider compatibility. Responses-only models are not supported by
this adapter. No real provider was contacted during local validation. Do not paste keys into chat or Git.

Provider charges, rate limits, model availability and free-tier eligibility are outside this project's
control. The default makes no provider calls. Input/output tokens are recorded when the endpoint returns
usage. Cost is `null` unless both per-million prices are configured; no current tariff is guessed.

Optional integration check, without changing packages:

```powershell
python -m scripts.doctor --full
```

The official adapter targets `mcp>=1.28,<2`. A pre-existing MCP 2.x installation is **not changed** by
the default doctor or required by the built-in path. Review version differences before using
`--full --install`; use a separate environment rather than downgrading a shared one blindly.

To require LangGraph and the official MCP adapter explicitly:

```dotenv
WORKFLOW_ENGINE=langgraph
MCP_IMPLEMENTATION=sdk
```

Then check:

```powershell
python -m scripts.mcp_smoke --implementation sdk
```

An unavailable explicitly requested engine/SDK is an error, not a silent fallback.

## 5. Live data

Select **Yahoo Finance** in the form. This requires `yfinance`, network access and a valid ticker.
The downloader explicitly requests adjusted daily closes. `start` is inclusive and `end` exclusive.
Missing observations are aligned by intersection; they are never forward-filled. A provider error
fails the run: it does **not** switch to synthetic prices.

Use same-currency assets with comparable trading sessions. The program warns about this constraint
but does not verify currencies or apply FX conversion. Point-in-time index membership, delisted-stock
coverage, news, fundamental statements and macroeconomic data are **not** supplied.

Demo fixtures cover weekdays from 2018-01-01 through 2025-12-31 for AAPL, MSFT, NVDA, JPM, SPY and QQQ.
These familiar symbols label **synthetic series**, not downloaded prices. The fixture does not model
exchange holidays. Its generator and fixed seeds are included.

## 6. Where everything runs

```text
Browser on your laptop
  -> FastAPI: app/main.py and app/api/routes.py
  -> bounded local worker: app/service.py
  -> LangGraph/native workflow: app/graph/workflow.py
  -> planner -> data -> quant -> risk -> critic -> report
  -> MCP client: app/tools/client.py
       -> market subprocess:   app/mcp_servers/market_server.py
       -> quant subprocess:    app/mcp_servers/quant_server.py
       -> database subprocess: app/mcp_servers/database_server.py
  -> deterministic tools / backtester / SQL
  -> data/runtime/ and browser results
```

You start **one command**. The application starts and cleans up MCP subprocesses itself.
Only LLM requests and live Yahoo requests leave your machine when those modes are explicitly enabled.
The front end has no CDN dependency or separate development server.

```text
app/
  agents/        Role logic and bounded model tool-call handling
  api/           REST endpoints and exports
  database/      SQLAlchemy models, sessions and parameterised queries
  graph/         Typed state, routing and optional LangGraph implementation
  mcp_servers/   Three real stdio servers; built-in and official SDK paths
  quant/         Signals, delayed-execution simulator and financial metrics
  tools/         Market data, quant/risk/verification tools and MCP client
  web/           Self-contained HTML, CSS and JavaScript
  main.py        FastAPI application
  service.py     Bounded worker execution, persistence and telemetry
  reporting.py   Evidence-based Markdown report
scripts/         Dependency doctor, launchers, demo, MCP checks and evaluation
skills/          Local SKILL.md instructions actually loaded by model-driven roles
tests/           Automated tests, including provider-response contract simulations
evals/           Fixed research-case definitions
examples/        Measured synthetic sample report and outputs
docs/            Architecture, methodology, testing and troubleshooting
validation/      Actual build-test logs and validation summary
data/fixtures/   Committed synthetic dataset
data/runtime/    Created automatically; ignored by Git
```

## 7. API and research memory

Open **http://127.0.0.1:8000/docs** for the bundled offline API reference or `/openapi.json` for the
machine-readable schema. `POST /api/research` returns a run ID. Poll `GET /api/research/{id}` or view
its `/events` endpoint. Statuses are `queued`, `running`, `completed`, `rejected`, `failed` and `interrupted`.
A completed run passed engineering checks; it did not establish financial significance.

SQLite tables `research_runs` and `agent_events` store the request, status, tool actions and results.
Data and backtest snapshots are SHA-256-addressed files under `data/runtime`. Keep both the database
and snapshot directories to preserve replay. The history tools use parameterised, bounded queries;
there is no unrestricted `run_sql` tool.

The queue is local and in-process, not durable or distributed. On restart, incomplete runs are marked
`interrupted` rather than falsely resumed. Use one application process. A public/multi-user service
would need authentication, isolation, a durable worker queue, deployment-specific migrations and monitoring.

## 8. Tests and evaluation

Check development packages first:

```powershell
python -m scripts.doctor --dev
python -m pytest -q
python -m scripts.mcp_smoke
python -m scripts.evaluate --transport local --engine native
python -m scripts.evaluate --transport mcp --engine native
```

Add `--dev --install` only when the doctor lists unsatisfied test dependencies. A real LLM evaluation
is separately requested with `--mode llm` and can incur charges. Simulated model contract tests do not
measure real model quality. See `validation/VALIDATION.md` for what was actually executed here and
what remains unverified; the GitHub Actions workflow is supplied, not claimed to have run.

To save your own resolved environment after a successful run:

```powershell
python -m pip freeze > requirements.local.lock.txt
```

The distributed requirements use bounded compatibility ranges, not a falsely claimed cross-platform
lockfile. The validation directory records the exact core versions used for this build.

## 9. Optional Docker/PostgreSQL

Create `.env` first. For the SQLite container setup:

```powershell
docker compose up --build
```

For PostgreSQL, set `POSTGRES_PASSWORD` in `.env`, then:

```powershell
docker compose -f compose.yaml -f compose.postgres.yaml up --build
```

Choose an alphanumeric password or correctly URL-encode reserved URL characters. Only localhost is
published. Named volumes persist data. These container configurations were not executed in the build
environment. Docker is a deployment option, **not** a claim that arbitrary model-generated code is safe.
This project never executes arbitrary model-generated Python or shell commands.

## 10. Further documentation

- `docs/METHODOLOGY.md`: exact timing, cash, costs, metrics and holdout definitions.
- `docs/ARCHITECTURE.md`: agent/tool boundaries, MCP messages, schemas and extension points.
- `docs/WINDOWS.md`: interpreter selection, PowerShell and OneDrive troubleshooting.
- `docs/SECURITY.md`: local-only boundary and specific protections.
- `validation/VALIDATION.md`: measured test results and honest verification limits.

## Primary technical references

Implementation was checked against these primary references; the app does not fetch them at runtime:

- LangGraph graph API: https://docs.langchain.com/oss/python/langgraph/use-graph-api
- MCP stdio transport: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- MCP lifecycle: https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
- MCP tools: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- Official MCP v1 SDK: https://py.sdk.modelcontextprotocol.io/v1/server/
- OpenAI function calling: https://developers.openai.com/api/docs/guides/function-calling
- yfinance download parameters: https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
- FastAPI lifespan: https://fastapi.tiangolo.com/advanced/events/

## Licence

Original project code and synthetic fixtures are MIT-licensed; see `LICENSE`.
External data and third-party packages retain their own terms. No real market dataset is redistributed.
