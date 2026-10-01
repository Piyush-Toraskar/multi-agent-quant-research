async def risk_agent(ctx, state):
    result = await ctx.execute_stage('risk_agent', [('assess_risk', {'artifact_id': state['backtest']['artifact_id']})], {'backtest': state['backtest']})
    return {'risk': result['assess_risk']}
