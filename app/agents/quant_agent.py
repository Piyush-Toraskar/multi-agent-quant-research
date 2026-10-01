async def quant_agent(ctx, state):
    dataset = state['data']['dataset_id']
    calls = [('analyse_market', {'dataset_id': dataset, 'lookback': state['request']['lookback']}),
             ('run_backtest', {'dataset_id': dataset, 'request': state['request'], 'strategy': state['plan']['strategy'],
                               'execution_delay': state.get('execution_delay', 1)})]
    result = await ctx.execute_stage('quant_agent', calls, {'plan': state['plan'], 'data': state['data'], 'revision': state.get('revision_note')})
    return {'analysis': result['analyse_market'], 'backtest': result['run_backtest']}
