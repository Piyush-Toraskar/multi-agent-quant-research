"""Small, deliberately scoped MCP 2025-06-18 stdio server.
Supports initialise/ping/tools. It does not claim the entire optional MCP surface.
Use MCP_IMPLEMENTATION=sdk for the official v1 SDK adapter below.
"""
import json
import sys
from app.config import Settings
from app.storage import sanitise
from app.tools.registry import registry

PROTOCOL_VERSION = '2025-06-18'
MAX_MESSAGE_BYTES = 4 * 1024 * 1024


def tool_result(value=None, error=None):
    if error is not None:
        return {'content': [{'type': 'text', 'text': str(error)}], 'isError': True}
    value = sanitise(value)
    return {'content': [{'type': 'text', 'text': json.dumps(value, allow_nan=False)}],
            'structuredContent': value, 'isError': False}


class Dispatcher:
    def __init__(self, group, settings):
        self.group = group
        self.settings = settings
        self.tools = {k: v for k, v in registry().items() if v.group == group}
        self.initialised = False
        self.ready = False

    def dispatch(self, message):
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or not isinstance(message.get('method'), str):
            return {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid Request'}}
        method = message['method']
        identifier = message.get('id')
        if 'id' not in message:
            if method == 'notifications/initialized' and self.initialised:
                self.ready = True
            return None
        def error(code, text):
            return {'jsonrpc': '2.0', 'id': identifier, 'error': {'code': code, 'message': text}}
        params = message.get('params', {})
        if not isinstance(params, dict):
            return error(-32602, 'Parameters must be an object')
        if method == 'initialize':
            if self.initialised:
                return error(-32600, 'Session is already initialised')
            if not isinstance(params.get('protocolVersion'), str) or not isinstance(params.get('clientInfo'), dict):
                return error(-32602, 'protocolVersion and clientInfo are required')
            self.initialised = True
            result = {'protocolVersion': PROTOCOL_VERSION, 'capabilities': {'tools': {'listChanged': False}},
                      'serverInfo': {'name': 'quant-' + self.group, 'version': '1.0.0'},
                      'instructions': 'Read-only research calculations; no brokerage, shell or arbitrary code tools.'}
        elif method == 'ping':
            result = {}
        elif not self.ready:
            return error(-32000, 'Complete initialisation before using tools')
        elif method == 'tools/list':
            if params.get('cursor'):
                return error(-32602, 'This small tool list is not paginated; cursor is invalid')
            result = {'tools': [tool.schema() for tool in self.tools.values()]}
        elif method == 'tools/call':
            if not isinstance(params.get('name'), str) or not isinstance(params.get('arguments', {}), dict):
                return error(-32602, 'Tool name must be a string and arguments must be an object')
            tool = self.tools.get(params.get('name'))
            if tool is None:
                return error(-32602, 'Unknown tool')
            try:
                result = tool_result(tool.call(self.settings, params.get('arguments', {})))
            except Exception as exc:
                result = tool_result(error=f'{type(exc).__name__}: {exc}')
        else:
            return error(-32601, 'Method not found')
        return {'jsonrpc': '2.0', 'id': identifier, 'result': result}


def serve_builtin(group, settings):
    dispatcher = Dispatcher(group, settings)
    while True:
        line = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
        if not line:
            return
        if len(line) > MAX_MESSAGE_BYTES:
            print('Incoming MCP message exceeds the configured size limit', file=sys.stderr)
            return
        try:
            message = json.loads(line)
            response = dispatcher.dispatch(message)
        except (ValueError, UnicodeError):
            response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}}
        if response is not None:
            sys.stdout.buffer.write((json.dumps(response, allow_nan=False) + '\n').encode('utf-8'))
            sys.stdout.buffer.flush()


async def serve_sdk(group, settings):
    # Kept behind an explicit configuration switch; this adapter targets mcp 1.x.
    from importlib.metadata import version
    if int(version('mcp').split('.')[0]) != 1:
        raise RuntimeError('Official SDK adapter requires mcp>=1.28,<2. Built-in transport supports the same local tools without that dependency.')
    from mcp import types
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server
    tools = {k: v for k, v in registry().items() if v.group == group}
    server = Server('quant-' + group)
    @server.list_tools()
    async def list_tools():
        return [types.Tool(**tool.schema()) for tool in tools.values()]
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name not in tools:
            raise ValueError('Unknown tool')
        value = tools[name].call(settings, arguments)
        # Text is a standard MCP tool result and is decoded by our client.
        return [types.TextContent(type='text', text=json.dumps(sanitise(value), allow_nan=False))]
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


def serve_group(group):
    settings = Settings(_env_file=None)
    settings.prepare()
    if settings.mcp_implementation == 'sdk':
        import asyncio
        asyncio.run(serve_sdk(group, settings))
    else:
        serve_builtin(group, settings)
