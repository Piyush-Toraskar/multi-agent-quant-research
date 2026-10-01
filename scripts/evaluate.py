"""Run fixed research cases; report measured completion/validity, not invented LLM accuracy."""
import argparse
import json
import tempfile
from pathlib import Path
from app.config import Settings, ROOT
from app.schemas import ResearchRequest
from app.database.queries import Repository
from app.service import execute_research, run_async


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--transport', choices=['local','mcp'], default='local')
    parser.add_argument('--engine', choices=['auto','native','langgraph'], default='auto')
    parser.add_argument('--mode', choices=['demo','llm'], default='demo')
    parser.add_argument('--output', default='data/runtime/evaluation.json')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    cases = json.loads((ROOT / 'evals' / 'cases.json').read_text())
    if args.offset < 0 or args.limit < 1:
        parser.error('offset must be non-negative and limit must be positive')
    cases = cases[args.offset:args.offset + args.limit]
    if not cases:
        parser.error('The selected case range is empty')
    results = []
    with tempfile.TemporaryDirectory(prefix='quant-eval-') as directory:
        settings = Settings(data_dir=Path(directory), database_url='sqlite:///' + Path(directory,'eval.db').as_posix(),
                            tool_transport=args.transport, workflow_engine=args.engine, agent_mode=args.mode)
        repository = Repository(settings)
        try:
            for case in cases:
                print('Evaluating:', case['name'], flush=True)
                values = ResearchRequest(**case['request']).model_dump(mode='json')
                run_id = repository.create(values)
                try:
                    state = await execute_research(settings, repository, run_id, values)
                    selected = state['plan']['strategy']
                    results.append({'case':case['name'], 'completed':True, 'checks_passed':state['verification']['passed'],
                        'expected_strategy':case['expected_strategy'], 'selected_strategy':selected,
                        'strategy_match':selected==case['expected_strategy'], 'telemetry':state['telemetry']})
                except Exception as exc:
                    results.append({'case':case['name'], 'completed':False, 'error':str(exc)})
        finally:
            repository.close()
    report = {'mode':args.mode, 'engine_requested':args.engine, 'transport':args.transport,
              'cases':len(results), 'completed':sum(x['completed'] for x in results),
              'checks_passed':sum(x.get('checks_passed',False) for x in results),
              'strategy_matches':sum(x.get('strategy_match',False) for x in results), 'results':results,
              'caveat':'Demo cases evaluate deterministic orchestration, not language-model performance. LLM mode incurs provider calls and is a separate evaluation.'}
    target=Path(args.output); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
    return 0 if report['checks_passed']==len(results) else 1

if __name__ == '__main__':
    raise SystemExit(run_async(main()))
