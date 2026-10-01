"""Inspect first. --install changes only missing/incompatible core requirements."""
import argparse
import importlib.metadata
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def requirements(path):
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if line.startswith('-r '):
            yield from requirements(path.parent / line[3:].strip())
        elif line:
            yield line


def main():
    parser = argparse.ArgumentParser(description='Check the active interpreter without modifying it by default')
    parser.add_argument('--install', action='store_true', help='Install only missing/incompatible requirements after showing the check')
    parser.add_argument('--full', action='store_true', help='Include optional LangGraph, official MCP SDK, yfinance and PostgreSQL driver')
    parser.add_argument('--dev', action='store_true', help='Include the test requirements')
    args = parser.parse_args()
    print('Python:', sys.version.split()[0]); print('Interpreter:', sys.executable); print('Project:', ROOT)
    if sys.version_info < (3, 11):
        print('ERROR: Python 3.11 or newer is required.'); return 2
    try:
        from packaging.requirements import Requirement
    except ImportError:
        from pip._vendor.packaging.requirements import Requirement
    filename = 'requirements.txt' if args.full else ('requirements-dev.txt' if args.dev else 'requirements-core.txt')
    needed = []
    for line in dict.fromkeys(requirements(ROOT / filename)):
        req = Requirement(line)
        try:
            version = importlib.metadata.version(req.name)
            okay = req.specifier.contains(version, prereleases=True)
            print(f'{req.name:24} {version:16} ' + ('OK' if okay else 'INCOMPATIBLE: ' + str(req.specifier)))
        except importlib.metadata.PackageNotFoundError:
            okay = False
            print(f'{req.name:24} {"MISSING":16} {req.specifier}')
        if not okay:
            needed.append(line)
    if needed:
        print('\nOnly these requirements need attention:', ', '.join(needed))
        print('Resolving them may also adjust shared transitive dependencies. A project virtual environment isolates that change.')
        if args.install:
            subprocess.run([sys.executable, '-m', 'pip', 'install', *needed], check=True)
            subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
        else:
            print('Nothing was changed. Add --install to this command to apply these requirements.')
            return 1
    else:
        print('\nAll checked requirements are satisfied. Nothing was installed or upgraded.')
    print('\nOptional modules:')
    for module in ['langgraph', 'mcp', 'yfinance', 'psycopg2', 'pytest']:
        print(' ', module, 'available' if importlib.util.find_spec(module) else 'not installed')
    print('\nStart from the project root: python -m app')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
