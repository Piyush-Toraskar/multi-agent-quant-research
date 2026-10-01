# Build validation

## Completed in this environment

- **85 tests passed; 2 optional-integration tests skipped.** Exact output: `pytest-results.txt`.
- **12 / 12 fixed research cases completed and passed engineering checks over direct tool calls.**
- **12 / 12 fixed research cases completed and passed engineering checks over real MCP stdio subprocesses.**
  The MCP cases were run in three batches of four. Full results and measured telemetry are included.
- The default full pipeline ran from the CLI and through the FastAPI application.
- A fresh extraction of the deliverable ZIP passed every manifest checksum, the read-only dependency check and the full native-orchestrator/MCP demo: six tool calls, zero failures and a generated report. No packages were installed. See `fresh-extraction.txt`.
- API tests cover submission, result polling, history, ordered events, report/JSON/CSV/snapshot exports,
  replay, invalid inputs and origin/host rejection.
- LLM contract tests use simulated provider responses and verify required tool calls, usage parsing,
  redacted errors and rejection of model attempts to change the approved data provider.
- Live-data adapter contract tests use simulated normal/MultiIndex price responses and failed downloads.
- A genuine critic revision loop and an unfixable-rejection path were exercised by controlled test fixtures.
- Python sources compiled successfully. `node --check app/web/app.js` passed. Node is only a build
  validation tool here, not an application dependency.
- Chromium/Playwright DOM tests checked form submission, a completed MCP-backed run, eight displayed
  critic checks, two chart series, five export links, absence of JavaScript page errors and layouts at
  1440 x 1100 and 390 x 844 without mobile horizontal overflow. The browser used a fetch bridge to
  the real FastAPI TestClient because browser navigation to localhost is blocked by this environment.
  This is not a claim of a fully unrestricted browser-to-TCP deployment test. Screenshots are in `docs/`.

## Not verified here

- Real LLM-provider requests, API credentials, model availability, tariffs or rate limits.
- Real Yahoo Finance network downloads and current provider data quality.
- LangGraph execution: its optional test is skipped because the package could not be installed here.
- The official MCP Python SDK adapter: its optional test is skipped for the same reason. The bundled
  MCP protocol implementation, not the SDK adapter, was exercised in actual subprocess tests.
- Docker builds, PostgreSQL deployment or a real Windows execution.
- Third-party MCP host interoperability or complete optional-feature conformance.
- Statistical significance, a real trading edge, latency suitable for HFT or production security.

The supplied GitHub Actions matrix is a workflow for the recipient to run; no successful remote CI
execution is claimed. Exact local core package versions are in `environment.json`. Requirements are
bounded ranges, not a tested cross-platform lockfile. Tests reduce risk but do not guarantee zero defects.

## Regression checks worth rerunning locally

```powershell
python -m scripts.doctor
python -m pytest -q
python -m scripts.demo
python -m scripts.mcp_smoke
```

Check `--full` before choosing LangGraph or the official SDK adapter; the default doctor makes no
package changes. Genuine LLM and live-data modes are explicit and never impersonated by demo output.
