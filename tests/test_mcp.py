import importlib.util
import pytest
from app.tools.client import ToolGateway
from app.mcp_servers.protocol import Dispatcher, PROTOCOL_VERSION


def initialise(d):
    reply=d.dispatch({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':PROTOCOL_VERSION,'clientInfo':{'name':'test','version':'1'}}})
    assert reply['result']['protocolVersion']==PROTOCOL_VERSION
    d.dispatch({'jsonrpc':'2.0','method':'notifications/initialized'})


def test_protocol_lifecycle(settings):
    d=Dispatcher('market',settings)
    assert 'error' in d.dispatch({'jsonrpc':'2.0','id':1,'method':'tools/list'})
    initialise(d)
    tools=d.dispatch({'jsonrpc':'2.0','id':2,'method':'tools/list'})['result']['tools']
    assert tools[0]['name']=='fetch_prices'
    assert d.dispatch({'jsonrpc':'2.0','id':3,'method':'ping'})['result']=={}


def test_unknown_method_and_tool(settings):
    d=Dispatcher('market',settings);initialise(d)
    assert d.dispatch({'jsonrpc':'2.0','id':2,'method':'bogus'})['error']['code']==-32601
    assert d.dispatch({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'shell'}})['error']['code']==-32602


def test_invalid_args_return_tool_error(settings):
    d=Dispatcher('market',settings);initialise(d)
    result=d.dispatch({'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'fetch_prices','arguments':{'request':{'query':'x'}}}})
    assert result['result']['isError'] is True


def test_invalid_jsonrpc_is_rejected(settings):
    d=Dispatcher('market',settings)
    assert d.dispatch(['not','an','object'])['error']['code']==-32600

@pytest.mark.integration
async def test_real_mcp_subprocess_discovery_and_calls(settings,request_data):
    settings.tool_transport='mcp'
    async with ToolGateway(settings) as gateway:
        assert len(gateway.schemas)==7
        dataset=await gateway.call('fetch_prices',{'request':request_data})
        result=await gateway.call('analyse_market',{'dataset_id':dataset['dataset_id'],'lookback':60})
        assert result['assets']['SPY']['beta_to_benchmark']==pytest.approx(1)
        history=await gateway.call('search_research',{'query':'','limit':1})
        assert history=={'runs':[]}
        with pytest.raises(ValueError,match='allow-listed'):
            await gateway.call('run_shell',{})

@pytest.mark.external
@pytest.mark.skipif(importlib.util.find_spec('mcp') is None,reason='Official MCP SDK is not installed in this test environment')
async def test_official_sdk_adapter(settings,request_data):
    from importlib.metadata import version
    if not version('mcp').startswith('1.'):
        pytest.skip('Official adapter intentionally targets mcp 1.x, not 2.x')
    settings.tool_transport='mcp';settings.mcp_implementation='sdk'
    async with ToolGateway(settings) as gateway:
        assert len(gateway.schemas)==7
        result=await gateway.call('fetch_prices',{'request':request_data})
        assert result['dataset_id']



def test_invalid_tool_name_type_does_not_crash_server(settings):
    d=Dispatcher('market',settings);initialise(d)
    reply=d.dispatch({'jsonrpc':'2.0','id':7,'method':'tools/call','params':{'name':[],'arguments':{}}})
    assert reply['error']['code']==-32602


def test_builtin_protocol_negotiates_known_version(settings):
    d=Dispatcher('market',settings)
    reply=d.dispatch({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2099-01-01','clientInfo':{}}})
    assert reply['result']['protocolVersion']==PROTOCOL_VERSION
