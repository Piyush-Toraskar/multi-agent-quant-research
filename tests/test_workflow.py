import importlib.util
import pytest
from app.service import execute_research
from app.graph.workflow import choose_engine
from app.agents.critic_agent import route_after_critic

@pytest.mark.parametrize('transport',['local','mcp'])
async def test_end_to_end(settings,repository,request_data,transport):
    settings.tool_transport=transport
    run_id=repository.create(request_data)
    state=await execute_research(settings,repository,run_id,request_data)
    assert state['verification']['passed']
    assert repository.get(run_id)['status']=='completed'
    assert state['telemetry']['tool_calls']==6
    assert state['telemetry']['llm_usage']['calls']==0
    assert 'SYNTHETIC' in state['report']
    assert state['backtest_detail']['trades']
    assert len(repository.events(run_id))>=25


def test_revision_routing_is_bounded(settings):
    state={'verification':{'passed':False,'revision':'increase_execution_delay'},'revisions':0}
    assert route_after_critic(state,settings)=='revise'
    state['revisions']=settings.max_revisions
    assert route_after_critic(state,settings)=='report'


async def test_failed_run_is_persisted(settings,repository,request_data):
    bad=dict(request_data,symbols=['UNKNOWN'])
    run_id=repository.create(bad)
    with pytest.raises(Exception):
        await execute_research(settings,repository,run_id,bad)
    assert repository.get(run_id)['status']=='failed'
    assert repository.get(run_id)['error']


async def test_replay_identical_results(settings,repository,request_data):
    a=await execute_research(settings,repository,repository.create(request_data),request_data)
    req=dict(request_data,snapshot_id=a['data']['dataset_id'],strategy=a['plan']['strategy'])
    b=await execute_research(settings,repository,repository.create(req),req)
    assert a['backtest_detail']['curve']==b['backtest_detail']['curve']
    assert a['backtest']['metrics']==b['backtest']['metrics']

@pytest.mark.external
@pytest.mark.skipif(importlib.util.find_spec('langgraph') is None,reason='LangGraph is not installed in this test environment')
async def test_langgraph_matches_native(settings,repository,request_data):
    native=await execute_research(settings,repository,repository.create(request_data),request_data)
    settings.workflow_engine='langgraph'
    graph=await execute_research(settings,repository,repository.create(request_data),request_data)
    assert graph['engine']=='langgraph'
    assert native['backtest']['metrics']==graph['backtest']['metrics']



async def test_actual_critic_revision_loop(settings,repository,request_data,monkeypatch):
    import app.tools.registry as reg
    original=reg.verify_research
    count=0
    def first_failure(settings,artifact_id,dataset_id):
        nonlocal count
        count+=1
        result=original(settings,artifact_id,dataset_id)
        if count==1:
            result.update(passed=False,failed=['future_perturbation'],revision='increase_execution_delay')
        return result
    monkeypatch.setattr(reg,'verify_research',first_failure)
    state=await execute_research(settings,repository,repository.create(request_data),request_data)
    assert state['verification']['passed'] and state['revisions']==1
    assert state['execution_delay']==2 and count==2
    assert state['telemetry']['tool_calls']==10


async def test_failed_critic_is_not_overridden(settings,repository,request_data,monkeypatch):
    import app.tools.registry as reg
    original=reg.verify_research
    def reject(settings,artifact_id,dataset_id):
        result=original(settings,artifact_id,dataset_id)
        result.update(passed=False,failed=['weights'],revision=None)
        return result
    monkeypatch.setattr(reg,'verify_research',reject)
    identifier=repository.create(request_data)
    state=await execute_research(settings,repository,identifier,request_data)
    assert repository.get(identifier)['status']=='rejected'
    assert '**REJECTED**' in state['report']
