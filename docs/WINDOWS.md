# Windows: where to run the code

## Use the project root

```powershell
cd C:\Users\Piyush\OneDrive\Desktop\TowerResearch\multi-agent-quant-research
python -m scripts.doctor
python -m app
```

Check that `Get-ChildItem` shows this README, `app` and `scripts`. A nested duplicate extraction is
the common cause of “No module named app”. Use module commands, not `python scripts/file.py`.

## Match pip to Python

```powershell
python -c "import sys; print(sys.executable)"
python -m pip --version
python -m pip check
```

These inspect the interpreter you are actually using. Dependencies installed under another Python
or another virtual environment do not automatically become available. Activate the existing project
venv or call its interpreter explicitly:

```powershell
.\.venv\Scripts\python.exe -m scripts.doctor
.\.venv\Scripts\python.exe -m app
```

Do not create a new venv and then assume the global packages are inside it. A normal new venv starts
isolated. The doctor is read-only until `--install` is supplied. Avoid a global upgrade of everything.

## Optional setup script

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

This process-local flag does not permanently change system execution policy. Add `-Install` only
after reviewing the dependency report. `-CreateVenv` explicitly creates and uses `.venv`; `-Full`
includes optional integrations. Existing `.env` is never overwritten.

The shortest launcher is `start.cmd`, which uses `python` on your current PATH. It does not pick a
venv automatically. The direct `python -m app` command is less ambiguous.

## Common messages

- **Address already in use:** stop the other process or use `python -m app --port 8001`.
- **Model/key missing:** demo needs neither; LLM mode requires both, then an application restart.
- **Yahoo data unavailable:** check symbol, dates, connectivity and provider limits. No synthetic fallback occurs.
- **MCP SDK requires 1.x:** stay on `MCP_IMPLEMENTATION=builtin`, or install the adapter's bounded version in an isolated environment.
- **No subprocess implementation:** use the supported `python -m app` entry point. The worker creates a Windows proactor loop.
- **Database locked / OneDrive synchronisation:** close duplicate app instances. SQLite is a local database, not a shared file service.
  Place runtime data outside the synchronised folder, for example `DATA_DIR=C:/Users/Piyush/quant-data` in `.env`.
- **Permission denied while extracting:** stop the existing app before replacing its source files. Do not overwrite an active database.

`.env` is optional for the offline defaults. It is not included in Git or the ZIP. Source-code changes
need an app restart; the default launcher intentionally does not use the development reloader.

## Optional installation from scratch

Only necessary on a machine without the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m scripts.doctor --install
.\.venv\Scripts\python.exe -m app
```

For optional integrations, first inspect `--full`; for tests inspect `--dev`. The supplied CI matrix
includes Windows but was not run in the Linux build environment, so its presence is not Windows test evidence.
