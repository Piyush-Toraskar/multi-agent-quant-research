import asyncio
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from app.agents.base import AgentContext
from app.agents.llm import LLMClient
from app.graph.workflow import run_workflow
from app.tools.client import ToolGateway
from app.storage import load_blob, sanitise


async def execute_research(settings, repository, run_id, request):
    started = time.perf_counter()
    repository.update(run_id, status='running')
    llm = None
    try:
        if settings.agent_mode == 'llm':
            llm = LLMClient(settings)
        async with ToolGateway(settings) as gateway:
            ctx = AgentContext(settings, repository, run_id, gateway, llm)
            state = await run_workflow(ctx, request)
            artifact = load_blob(settings.data_dir / 'artifacts', state['backtest']['artifact_id'])
            state['backtest_detail'] = artifact
            state['agent_notes'] = ctx.agent_notes
            state['telemetry'] = {'elapsed_seconds': time.perf_counter() - started,
                'tool_calls': ctx.tool_calls, 'tool_failures': ctx.tool_failures,
                'invalid_model_calls': ctx.invalid_model_calls, 'revision_count': state['revisions'],
                'llm_usage': dict(llm.usage) if llm else {'input_tokens': 0, 'output_tokens': 0, 'calls': 0, 'http_attempts': 0},
                'estimated_llm_cost_usd': llm.cost_estimate() if llm else 0.0,
                'agent_mode': settings.agent_mode, 'tool_transport': settings.tool_transport,
                'mcp_implementation': settings.mcp_implementation if settings.tool_transport == 'mcp' else None}
        repository.update(run_id, status='completed' if state['verification']['passed'] else 'rejected', result=sanitise(state), error=None)
        return state
    except Exception as exc:
        # HTTP adapter redacts provider errors. Last-line redaction protects configured credentials.
        message = f'{type(exc).__name__}: {exc}'
        if settings.api_key:
            message = message.replace(settings.api_key, '[REDACTED]')
        repository.update(run_id, status='failed', error=message[:1500])
        repository.event(run_id, 'orchestrator', 'error', {'message': message[:1500]})
        raise
    finally:
        if llm:
            await llm.close()


def run_async(coroutine):
    # Uvicorn on Windows can run a selector loop. MCP subprocesses get their own
    # proactor-capable loop in the worker thread instead of inheriting that loop.
    if sys.platform == 'win32':
        with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
            return runner.run(coroutine)
    return asyncio.run(coroutine)


class ResearchService:
    def __init__(self, settings, repository):
        self.settings, self.repository = settings, repository
        self.pool = ThreadPoolExecutor(max_workers=settings.max_workers, thread_name_prefix='quant-run')
        self.capacity = threading.BoundedSemaphore(settings.max_pending_runs)
        self.futures = set()
        self.lock = threading.Lock()

    def submit(self, request):
        if not self.capacity.acquire(blocking=False):
            raise RuntimeError('Research queue is full; wait for an existing run to finish')
        try:
            values = request.model_dump(mode='json')
            run_id = self.repository.create(values)
            future = self.pool.submit(run_async, execute_research(self.settings, self.repository, run_id, values))
            with self.lock:
                self.futures.add(future)
            def finished(f):
                # Consume exceptions: the database contains the actionable error for the UI.
                try:
                    f.exception()
                finally:
                    with self.lock:
                        self.futures.discard(f)
                    self.capacity.release()
            future.add_done_callback(finished)
            return run_id
        except Exception:
            self.capacity.release()
            raise

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=False)
