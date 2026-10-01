"""Contract tests use synthetic model responses. These are NOT live provider tests."""
import json
import httpx
import pytest
from app.agents.llm import LLMClient
from app.service import execute_research
from app.agents.planner import deterministic_plan

class ModelSimulator:
    def __init__(self,settings):
        self.usage={'input_tokens':0,'output_tokens':0,'calls':0,'http_attempts':0}
    async def close(self):
        pass
    def cost_estimate(self):
        return None
    async def complete(self,messages,tools=None,required=False):
        self.usage['calls']+=1
        if tools[0]['function']['name']=='submit_research_plan':
            request=json.loads(messages[1]['content'])['request']
            args=deterministic_plan(request)
            return {'role':'assistant','content':None,'tool_calls':[{'id':'plan1','type':'function','function':{'name':'submit_research_plan','arguments':json.dumps(args)}}]}
        if any(m['role']=='tool' for m in messages):
            return {'role':'assistant','content':'Completed the approved tool calls.'}
        approved=json.loads(messages[1]['content'])['approved_calls']
        return {'role':'assistant','content':None,'tool_calls':[
            {'id':'call'+str(i),'type':'function','function':{'name':name,'arguments':json.dumps(args)}} for i,(name,args) in enumerate(approved)]}


async def test_full_llm_contract_with_simulated_responses(settings,repository,request_data,monkeypatch):
    import app.service
    settings.agent_mode='llm'
    monkeypatch.setattr(app.service,'LLMClient',ModelSimulator)
    run_id=repository.create(request_data)
    state=await execute_research(settings,repository,run_id,request_data)
    assert state['verification']['passed']
    assert state['telemetry']['llm_usage']['calls']==9
    assert state['telemetry']['tool_calls']==6
    assert state['telemetry']['invalid_model_calls']==0


async def test_llm_http_contract_and_usage(settings,monkeypatch):
    settings.llm_model='test-model'
    # Assignment is intentionally validated through a reconstructed Settings object.
    from app.config import Settings
    settings=Settings(_env_file=None,**{**settings.model_dump(),'llm_api_key':'test-secret'})
    client=LLMClient(settings)
    async def post(url,**kwargs):
        assert url.endswith('/chat/completions')
        assert kwargs['headers']['Authorization']=='Bearer test-secret'
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'done'}}],
                                       'usage':{'prompt_tokens':12,'completion_tokens':4}})
    monkeypatch.setattr(client.client,'post',post)
    try:
        reply=await client.complete([{'role':'user','content':'hello'}])
        assert reply['content']=='done'
        assert client.usage['input_tokens']==12 and client.usage['output_tokens']==4
    finally:
        await client.close()


async def test_api_key_not_in_error(settings,monkeypatch):
    from app.config import Settings
    settings=Settings(_env_file=None,llm_model='test',llm_api_key='SECRET')
    client=LLMClient(settings)
    async def post(*args,**kwargs):
        return httpx.Response(401,text='SECRET is invalid')
    monkeypatch.setattr(client.client,'post',post)
    try:
        with pytest.raises(RuntimeError) as exc:
            await client.complete([])
        assert 'SECRET' not in str(exc.value)
    finally:
        await client.close()


def test_llm_requires_explicit_configuration(settings):
    with pytest.raises(ValueError,match='requires'):
        LLMClient(settings)



async def test_model_cannot_change_approved_data_provider(settings,repository,request_data,monkeypatch):
    import app.service
    class RetrySimulator(ModelSimulator):
        data_attempt=0
        async def complete(self,messages,tools=None,required=False):
            if tools[0]['function']['name']=='fetch_prices':
                self.data_attempt+=1
                if self.data_attempt==1:
                    message=await super().complete(messages,tools,required)
                    args=json.loads(message['tool_calls'][0]['function']['arguments'])
                    args['request']['provider']='yfinance'
                    message['tool_calls'][0]['function']['arguments']=json.dumps(args)
                    return message
                if self.data_attempt==2:
                    return await super().complete(messages[:2],tools,required)
            return await super().complete(messages,tools,required)
    settings.agent_mode='llm'
    monkeypatch.setattr(app.service,'LLMClient',RetrySimulator)
    state=await execute_research(settings,repository,repository.create(request_data),request_data)
    assert state['data']['metadata']['provider']=='demo'
    assert state['telemetry']['invalid_model_calls']==1
    assert state['verification']['passed']
