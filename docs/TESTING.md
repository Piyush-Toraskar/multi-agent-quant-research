# Tests and what they establish

`python -m pytest -q` runs local tests. No actual LLM or Yahoo requests are made by the default tests.
Provider simulations are explicitly described as contract tests, not integration with a real account.
The official MCP SDK and LangGraph tests skip with a reason when the dependency is absent.

Coverage includes input limits, non-finite values, immutable hashes, date alignment, duplicate dates,
synthetic reproducibility, live-provider response shapes and failure behaviour, metric formulas,
first-day drawdown, next-close execution, fee accounting, drifting weights, warm-up, all strategies,
future-price perturbation, chronological holdout, SQL injection strings, run/event persistence,
MCP initialisation/errors/discovery/subprocess calls, full local/MCP workflows, revision and rejection,
LLM tool contracts and attempted argument changes, API validation/exports/replay and browser security headers.

`python -m scripts.evaluate` runs fixed, self-authored research cases and records completion,
strategy selection, engineering-check results and measured telemetry. This is a small regression suite,
not a statistical benchmark of agent quality. In demo mode its routing score is deterministic-policy
accuracy, not LLM accuracy. A genuine provider evaluation requires explicit `--mode llm` and credentials.

Use `--limit` and `--offset` for smaller evaluation batches. The complete default list is in `evals/cases.json`.
Source/output contracts are deliberately bounded; they do not establish investment performance.
See `validation/VALIDATION.md` for the actual build environment, completed checks and unverified items.
