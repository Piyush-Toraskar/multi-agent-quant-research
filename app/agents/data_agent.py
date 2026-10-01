async def data_agent(ctx, state):
    result = await ctx.execute_stage('data_agent', [('fetch_prices', {'request': state['request']})], {'plan': state['plan']})
    return {'data': result['fetch_prices']}
