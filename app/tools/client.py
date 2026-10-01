"""A bounded, sequential-per-connection MCP stdio client and a direct-call adapter."""
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from app.config import ROOT
from app.mcp_servers.protocol import PROTOCOL_VERSION, MAX_MESSAGE_BYTES
from app.tools.registry import registry


class MCPError(RuntimeError):
    pass


class StdioClient:
    def __init__(self, group, settings):
        self.group, self.settings = group, settings
        self.process = None
        self.sequence = 0
        self.lock = asyncio.Lock()
        self.stderr_task = None
        self.stderr_tail = ''

    async def __aenter__(self):
        keep = ['PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP', 'HOME',
                'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'VIRTUAL_ENV', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
                'HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY']
        env = {key: value for key, value in os.environ.items() if key.upper() in keep}
        env.update(self.settings.child_env())
        env.update(PYTHONPATH=str(ROOT), PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
                   OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'app.mcp_servers.' + self.group + '_server',
            cwd=str(ROOT), env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=MAX_MESSAGE_BYTES + 1024)
        self.stderr_task = asyncio.create_task(self._drain_stderr())
        try:
            info = await self.request('initialize', {'protocolVersion': PROTOCOL_VERSION, 'capabilities': {},
                                                   'clientInfo': {'name': 'quant-research', 'version': '1.0.0'}})
            if info.get('protocolVersion') != PROTOCOL_VERSION or 'tools' not in info.get('capabilities', {}):
                raise MCPError('MCP server did not negotiate the supported protocol/tools capability')
            await self.notify('notifications/initialized')
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def _drain_stderr(self):
        while True:
            chunk = await self.process.stderr.read(2048)
            if not chunk:
                return
            self.stderr_tail = (self.stderr_tail + chunk.decode('utf-8', errors='replace'))[-8000:]

    async def notify(self, method, params=None):
        message = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            message['params'] = params
        self.process.stdin.write((json.dumps(message, allow_nan=False) + '\n').encode('utf-8'))
        await self.process.stdin.drain()

    async def request(self, method, params=None):
        async with self.lock:
            self.sequence += 1
            identifier = self.sequence
            message = {'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params or {}}
            payload = (json.dumps(message, allow_nan=False) + '\n').encode('utf-8')
            if len(payload) > MAX_MESSAGE_BYTES:
                raise MCPError('Tool arguments exceed the configured message limit')
            self.process.stdin.write(payload)
            await self.process.stdin.drain()
            try:
                async with asyncio.timeout(self.settings.tool_timeout_seconds):
                    while True:
                        line = await self.process.stdout.readline()
                        if not line:
                            raise MCPError('MCP ' + self.group + ' process exited: ' + self.stderr_tail[-800:])
                        reply = json.loads(line)
                        if 'id' not in reply:
                            continue  # Standard server notification.
                        if reply.get('id') != identifier:
                            raise MCPError('Unexpected MCP response identifier')
                        if 'error' in reply:
                            raise MCPError(str(reply['error'].get('message', 'Protocol error')))
                        if 'result' not in reply:
                            raise MCPError('Missing MCP response result')
                        return reply['result']
            except TimeoutError as exc:
                # Closing the process after a timeout is intentional: no late response can
                # be confused with a subsequent request, and synchronous work is stopped.
                try:
                    await self.notify('notifications/cancelled', {'requestId': identifier, 'reason': 'Timeout'})
                finally:
                    if self.process.returncode is None:
                        self.process.terminate()
                raise MCPError('MCP tool timeout in ' + self.group) from exc

    async def call(self, name, arguments):
        result = await self.request('tools/call', {'name': name, 'arguments': arguments})
        text = '\n'.join(item.get('text', '') for item in result.get('content', []) if item.get('type') == 'text')
        if result.get('isError'):
            raise MCPError(text)
        value = result.get('structuredContent')
        if value is None:
            value = json.loads(text)
        if not isinstance(value, dict):
            raise MCPError('Expected an object-valued tool result')
        return value

    async def __aexit__(self, *args):
        if not self.process:
            return
        # Drain both output pipes during shutdown. asyncio's Process.wait() can
        # otherwise wait on pipe closure even after the child has exited.
        async def drain_stdout():
            while await self.process.stdout.read(65536):
                pass
        stdout_task = asyncio.create_task(drain_stdout())
        try:
            if self.process.stdin and not self.process.stdin.is_closing():
                self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), 3)
            except TimeoutError:
                if self.process.returncode is None:
                    try:
                        self.process.terminate()
                    except ProcessLookupError:
                        pass
                try:
                    await asyncio.wait_for(self.process.wait(), 2)
                except TimeoutError:
                    if self.process.returncode is None:
                        try:
                            self.process.kill()
                        except ProcessLookupError:
                            pass
                    await asyncio.wait_for(self.process.wait(), 2)
        finally:
            for task in [stdout_task, self.stderr_task]:
                if task is not None:
                    try:
                        await asyncio.wait_for(asyncio.shield(task), 2)
                    except (TimeoutError, asyncio.CancelledError):
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)



class ToolGateway:
    def __init__(self, settings):
        self.settings = settings
        self.tools = registry()
        self.clients = {}
        self.schemas = {}
        self.stack = AsyncExitStack()

    async def __aenter__(self):
        await self.stack.__aenter__()
        try:
            if self.settings.tool_transport == 'mcp':
                for group in ['market', 'quant', 'database']:
                    client = await self.stack.enter_async_context(StdioClient(group, self.settings))
                    self.clients[group] = client
                    response = await client.request('tools/list')
                    for tool in response['tools']:
                        if tool['name'] in self.tools and self.tools[tool['name']].group == group:
                            self.schemas[tool['name']] = tool
                if set(self.schemas) != set(self.tools):
                    raise MCPError('Expected MCP tools were not discovered')
            else:
                self.schemas = {name: tool.schema() for name, tool in self.tools.items()}
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *args):
        await self.stack.__aexit__(*args)

    async def call(self, name, arguments):
        if name not in self.tools:
            raise ValueError('Tool is not allow-listed: ' + str(name))
        tool = self.tools[name]
        # Validate on both sides of the boundary.
        values = tool.model.model_validate(arguments).model_dump(mode='json')
        if self.settings.tool_transport == 'mcp':
            return await self.clients[tool.group].call(name, values)
        return await asyncio.to_thread(tool.call, self.settings, values)
