import importlib.util
from app.graph.state import ResearchState
from app.agents.planner import planner
from app.agents.data_agent import data_agent
from app.agents.quant_agent import quant_agent
from app.agents.risk_agent import risk_agent
from app.agents.critic_agent import critic_agent, revise, route_after_critic
from app.agents.report_agent import report_agent

NODES = {'planner': planner, 'data': data_agent, 'quant': quant_agent, 'risk': risk_agent,
         'critic': critic_agent, 'revise': revise, 'report': report_agent}


def choose_engine(settings):
    present = importlib.util.find_spec('langgraph') is not None
    if settings.workflow_engine == 'langgraph' and not present:
        raise RuntimeError('WORKFLOW_ENGINE=langgraph requires the langgraph package. Install it or choose native.')
    if settings.workflow_engine == 'auto':
        return 'langgraph' if present else 'native'
    return settings.workflow_engine


async def run_workflow(ctx, request):
    engine = choose_engine(ctx.settings)
    initial = {'request': request, 'engine': engine, 'execution_delay': 1, 'revisions': 0}
    ctx.event('orchestrator', 'workflow_start', engine=engine, transport=ctx.settings.tool_transport,
              discovered_tools=list(ctx.gateway.schemas), agent_mode=ctx.settings.agent_mode)
    if engine == 'langgraph':
        from langgraph.graph import StateGraph, START, END
        builder = StateGraph(ResearchState)
        def wrap(fn):
            async def node(state):
                return await fn(ctx, state)
            return node
        for name, fn in NODES.items():
            builder.add_node(name, wrap(fn))
        builder.add_edge(START, 'planner')
        for a, b in [('planner','data'), ('data','quant'), ('quant','risk'), ('risk','critic'), ('revise','quant')]:
            builder.add_edge(a, b)
        builder.add_conditional_edges('critic', lambda state: route_after_critic(state, ctx.settings), {'report':'report', 'revise':'revise'})
        builder.add_edge('report', END)
        return await builder.compile().ainvoke(initial, {'recursion_limit': 40})
    state = dict(initial)
    node = 'planner'
    next_nodes = {'planner':'data', 'data':'quant', 'quant':'risk', 'risk':'critic', 'revise':'quant'}
    for _ in range(40):
        state.update(await NODES[node](ctx, state))
        if node == 'report':
            return state
        node = route_after_critic(state, ctx.settings) if node == 'critic' else next_nodes[node]
    raise RuntimeError('Workflow step budget exceeded')
