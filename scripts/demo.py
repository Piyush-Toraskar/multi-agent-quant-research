import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Run a complete offline experiment from the terminal')
    parser.add_argument('--transport', choices=['mcp', 'local'], default='mcp')
    parser.add_argument('--engine', choices=['auto', 'native', 'langgraph'], default='auto')
    parser.add_argument('--output', default='data/runtime/demo_report.md')
    args = parser.parse_args()
    from app.config import Settings
    from app.schemas import ResearchRequest
    from app.database.queries import Repository
    from app.service import execute_research, run_async
    settings = Settings(agent_mode='demo', tool_transport=args.transport, workflow_engine=args.engine)
    repository = Repository(settings)
    request = ResearchRequest().model_dump(mode='json')
    run_id = repository.create(request)
    try:
        result = run_async(execute_research(settings, repository, run_id, request))
        target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result['report'], encoding='utf-8')
        print('Run:', run_id)
        print('Source:', result['data']['metadata']['source'])
        print('Engine:', result['engine'], '| Tool transport:', args.transport)
        print('Critic checks:', 'PASSED' if result['verification']['passed'] else 'REJECTED')
        print('Report:', target.resolve())
        print(json.dumps(result['telemetry'], indent=2))
    finally:
        repository.close()

if __name__ == '__main__':
    main()
