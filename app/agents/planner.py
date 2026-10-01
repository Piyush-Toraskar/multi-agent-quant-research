import json
from app.schemas import Plan
from app.agents.llm import function_schema, decode_call


def deterministic_plan(request):
    query = request['query'].lower()
    strategy = request['strategy']
    if strategy == 'auto':
        if any(word in query for word in ['moving average', 'crossover', 'sma']):
            strategy = 'sma_cross'
        elif any(word in query for word in ['buy and hold', 'buy-and-hold', 'buy hold', 'buy_hold']):
            strategy = 'buy_hold'
        else:
            strategy = 'momentum'
    return Plan(strategy=strategy,
        hypothesis={'momentum': 'Positive trailing price momentum may persist into later returns.',
                    'sma_cross': 'A fast moving average above a slow moving average may identify persistent upward trends.',
                    'buy_hold': 'An equal-allocation long-only reference portfolio provides a baseline.'}[strategy],
        rationale='Compare a fixed, explicitly parameterised strategy with the benchmark and a chronological holdout. No parameter optimisation.').model_dump()


async def planner(ctx, state):
    request = state['request']
    ctx.event('planner', 'agent_start', mode=ctx.settings.agent_mode)
    # Database MCP is genuinely exercised; earlier runs are context, not new evidence.
    history = await ctx.call('planner', 'search_research', {'query': request['symbols'][0], 'limit': 3})
    if ctx.llm is None:
        plan = deterministic_plan(request)
    else:
        schema = function_schema('submit_research_plan', 'Propose one supported research hypothesis and strategy. Explicit strategy selection is binding.', Plan.model_json_schema())
        messages = [{'role': 'system', 'content': ctx.skill('planner') + '\nUse submit_research_plan. User form fields are authoritative. Do not alter dates, tickers, costs or windows.'},
                    {'role': 'user', 'content': json.dumps({'request': request, 'previous_runs': history})}]
        plan = None
        for _ in range(ctx.settings.max_agent_turns):
            message = await ctx.llm.complete(messages, [schema], required=True)
            calls = message.get('tool_calls') or []
            try:
                if len(calls) != 1:
                    raise ValueError('Submit exactly one plan')
                name, args = decode_call(calls[0])
                if name != 'submit_research_plan':
                    raise ValueError('Unknown planning tool')
                plan = Plan.model_validate(args).model_dump()
                if request['strategy'] != 'auto' and plan['strategy'] != request['strategy']:
                    raise ValueError('Explicit strategy selection must be honoured')
                break
            except (ValueError, KeyError, TypeError) as exc:
                plan = None
                ctx.invalid_model_calls += 1
                ctx.event('planner', 'invalid_model_call', error=str(exc)[:500])
                # Start a fresh, valid message history rather than leaving unpaired tool messages.
                messages.append({'role': 'user', 'content': 'The last plan was invalid: ' + str(exc)[:500]})
        if plan is None:
            raise RuntimeError('Planner failed to produce a valid research plan')
    ctx.event('planner', 'agent_end', plan=plan)
    return {'plan': plan, 'history': history}
