import csv
import io
import json
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from app.schemas import ResearchRequest
from app.storage import load_blob
from app.graph.workflow import choose_engine

router = APIRouter(prefix='/api')


def repo(request):
    return request.app.state.repository


def get_run(request, run_id):
    row = repo(request).get(run_id)
    if row is None:
        raise HTTPException(404, 'Research run not found')
    return row


@router.get('/health')
def health(request: Request):
    settings = request.app.state.settings
    return {'status': 'ok', 'version': '1.0.0', 'agent_mode': settings.agent_mode,
            'workflow_engine': choose_engine(settings), 'tool_transport': settings.tool_transport,
            'mcp_implementation': settings.mcp_implementation,
            'llm_configured': bool(settings.api_key and settings.llm_model)}


@router.post('/research', status_code=202)
def create_research(body: ResearchRequest, request: Request):
    try:
        run_id = request.app.state.service.submit(body)
    except RuntimeError as exc:
        raise HTTPException(429, str(exc)) from exc
    return {'id': run_id, 'status': 'queued'}


@router.get('/research')
def research_history(request: Request, query: str = Query('', max_length=200), limit: int = Query(30, ge=1, le=100)):
    return {'runs': repo(request).search(query, limit)}


@router.get('/research/{run_id}')
def research_result(run_id: str, request: Request):
    return get_run(request, run_id)


@router.get('/research/{run_id}/events')
def research_events(run_id: str, request: Request, after: int = Query(0, ge=0)):
    get_run(request, run_id)
    return {'events': repo(request).events(run_id, after)}


@router.get('/research/{run_id}/report', response_class=PlainTextResponse)
def report(run_id: str, request: Request):
    row = get_run(request, run_id)
    if not row['result']:
        raise HTTPException(409, 'Report is not available yet')
    return PlainTextResponse(row['result']['report'], media_type='text/markdown',
        headers={'Content-Disposition': f'attachment; filename="research-{row["id"]}.md"'})


@router.get('/research/{run_id}/export/{format}')
def export(run_id: str, format: str, request: Request):
    row = get_run(request, run_id)
    if not row['result']:
        raise HTTPException(409, 'Results are not available yet')
    result = row['result']
    if format == 'json':
        content, media, suffix = json.dumps(row, indent=2, allow_nan=False), 'application/json', 'json'
    elif format in {'curve', 'trades'}:
        entries = result['backtest_detail']['curve' if format == 'curve' else 'trades']
        buffer = io.StringIO(newline='')
        fields = (['date', 'equity', 'benchmark_equity', 'return', 'benchmark_return', 'cost', 'turnover', 'exposure']
                  if format == 'curve' else ['date', 'signal_date', 'symbol', 'side', 'notional', 'cost'])
        writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(entries)
        content, media, suffix = buffer.getvalue(), 'text/csv', format + '.csv'
    elif format == 'snapshot':
        content = json.dumps(load_blob(request.app.state.settings.data_dir / 'snapshots', result['data']['dataset_id']), indent=2)
        media, suffix = 'application/json', 'snapshot.json'
    else:
        raise HTTPException(404, 'Use json, curve, trades or snapshot')
    return Response(content, media_type=media, headers={'Content-Disposition': f'attachment; filename="research-{row["id"]}.{suffix}"'})


@router.post('/research/{run_id}/replay', status_code=202)
def replay(run_id: str, request: Request):
    row = get_run(request, run_id)
    if not row['result']:
        raise HTTPException(409, 'This run has no replayable dataset')
    values = dict(row['request'])
    values['snapshot_id'] = row['result']['data']['dataset_id']
    values['strategy'] = row['result']['plan']['strategy']
    try:
        new_id = request.app.state.service.submit(ResearchRequest.model_validate(values))
    except RuntimeError as exc:
        raise HTTPException(429, str(exc)) from exc
    return {'id': new_id, 'status': 'queued'}
