async def critic_agent(ctx, state):
    result = await ctx.execute_stage('critic_agent', [('verify_research', {'artifact_id': state['backtest']['artifact_id'],
             'dataset_id': state['data']['dataset_id']})], {'plan': state['plan'], 'backtest': state['backtest'], 'risk': state['risk']})
    verification = result['verify_research']
    # An LLM summary never overrides deterministic acceptance criteria.
    return {'verification': verification}


def route_after_critic(state, settings):
    if state['verification']['passed']:
        return 'report'
    if state['verification'].get('revision') == 'increase_execution_delay' and state.get('revisions', 0) < settings.max_revisions:
        return 'revise'
    return 'report'  # Deliver a clearly rejected report, not a silently accepted run.


async def revise(ctx, state):
    delay = min(3, state.get('execution_delay', 1) + 1)
    ctx.event('critic_agent', 'revision', execution_delay=delay, failed=state['verification']['failed'])
    return {'execution_delay': delay, 'revisions': state.get('revisions', 0) + 1,
            'revision_note': 'Critic requested a stricter execution delay; record both attempts.'}
