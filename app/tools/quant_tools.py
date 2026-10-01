import numpy as np
import pandas as pd
from app.tools.market_data import load_dataset
from app.quant.metrics import performance, beta
from app.quant.backtest import run_engine
from app.storage import sanitise, save_blob, load_blob


def analyse_market(settings, dataset_id, lookback=60):
    prices, metadata = load_dataset(settings, dataset_id)
    returns = prices.pct_change(fill_method=None).iloc[1:]
    benchmark = metadata['benchmark']
    result = {}
    for symbol in prices.columns:
        values = performance(returns[symbol], baseline_date=prices.index[0])
        values['beta_to_benchmark'] = beta(returns[symbol], returns[benchmark])
        values['latest_price'] = float(prices[symbol].iloc[-1])
        values['trailing_momentum'] = float(prices[symbol].iloc[-1] / prices[symbol].iloc[-lookback-1] - 1) if len(prices) > lookback else None
        values['rolling_20d_volatility'] = float(returns[symbol].iloc[-20:].std(ddof=1) * np.sqrt(252))
        result[str(symbol)] = values
    return sanitise({'dataset_id': dataset_id, 'assets': result, 'correlation': returns.corr().to_dict(),
                     'factor': {'name': 'trailing_price_momentum', 'lookback': lookback,
                                'note': 'Descriptive price factor, not a causal test or a multi-factor attribution model.'}})


def run_backtest(settings, dataset_id, request, strategy, execution_delay=1):
    prices, metadata = load_dataset(settings, dataset_id)
    result = run_engine(prices, request, strategy, execution_delay)
    result.update(dataset_id=dataset_id, source=metadata['source'])
    identifier = save_blob(settings.data_dir / 'artifacts', result)
    return {'artifact_id': identifier, 'dataset_id': dataset_id, 'strategy': strategy,
            'metrics': result['metrics'], 'trade_count': result['trade_count'],
            'total_cost': result['total_cost'], 'total_turnover': result['total_turnover'],
            'holdout_start': result['holdout_start'], 'execution_delay': execution_delay}


def assess_risk(settings, artifact_id):
    result = load_blob(settings.data_dir / 'artifacts', artifact_id)
    rows = result['curve'][1:]
    r = pd.Series([x['return'] for x in rows])
    b = pd.Series([x['benchmark_return'] for x in rows])
    tail = sorted(rows, key=lambda row: row['return'])[:5]
    exposures = [row['exposure'] for row in rows]
    checks = {'long_only': all(min(row['end_weights']) >= -1e-10 for row in rows),
              'unlevered': max(exposures) <= 1 + 1e-9,
              'positive_equity': all(row['equity'] > 0 for row in rows)}
    return sanitise({'artifact_id': artifact_id, 'checks': checks,
        'beta_to_benchmark': beta(r, b), 'average_exposure': float(np.mean(exposures)),
        'max_exposure': float(max(exposures)), 'max_single_asset_weight': float(max(max(row['end_weights']) for row in rows)),
        'historical_var_95': result['metrics']['strategy']['historical_var_95'],
        'historical_cvar_95': result['metrics']['strategy']['historical_cvar_95'],
        'worst_days': [{'date': row['date'], 'return': row['return']} for row in tail],
        'stress_scenario': {'description': 'One-period -20% shock to every risky asset at final portfolio weights; illustrative, not a forecast.',
                            'portfolio_loss': float(0.2 * exposures[-1])}})
