"""Long-only, fractional-unit, self-financing close-to-close simulator.
Signals from close t may be executed only at a later close. Portfolio weights drift
between rebalances; trading costs are solved against post-cost target NAV.
"""
import numpy as np
import pandas as pd
from app.schemas import ResearchRequest
from app.quant.strategies import target_weights, decision_schedule
from app.quant.metrics import performance
from app.storage import sanitise


def simulate(prices, targets, due, execution_delay, capital, cost_bps):
    if execution_delay < 1:
        raise ValueError('Execution delay must be at least one complete close')
    prices = prices.astype(float)
    if not np.isfinite(prices.to_numpy()).all() or (prices.to_numpy() <= 0).any():
        raise ValueError('Invalid prices')
    if not prices.index.equals(targets.index) or not prices.columns.equals(targets.columns):
        raise ValueError('Targets and prices must align exactly')
    if not np.isfinite(targets.to_numpy()).all():
        raise ValueError('Targets must be finite')
    if (targets.to_numpy() < 0).any() or (targets.sum(axis=1) > 1 + 1e-10).any():
        raise ValueError('Long-only weights must sum to at most one')
    returns = prices.pct_change(fill_method=None).fillna(0).to_numpy()
    planned = targets.shift(execution_delay).fillna(0).to_numpy()
    executions = due.shift(execution_delay, fill_value=False).to_numpy()
    weights = np.zeros(prices.shape[1])
    nav = float(capital)
    rate = cost_bps / 10000
    records, trades = [], []
    for i, day in enumerate(prices.index):
        beginning = weights.copy()
        before = nav * (1 + float(beginning @ returns[i]))
        drift = beginning * (1 + returns[i]) / (before / nav)
        fee, turnover = 0.0, 0.0
        if executions[i]:
            target = planned[i]
            fraction = 0.0
            for _ in range(30):
                next_fraction = rate * float(np.abs(target * (1 - fraction) - drift).sum())
                if abs(next_fraction - fraction) < 1e-14:
                    fraction = next_fraction
                    break
                fraction = next_fraction
            notionals = before * (target * (1 - fraction) - drift)
            turnover = float(np.abs(notionals).sum() / before)
            fee = before * fraction
            for j, symbol in enumerate(prices.columns):
                if abs(notionals[j]) > 1e-7:
                    trades.append({'date': day.strftime('%Y-%m-%d'), 'signal_date': prices.index[i-execution_delay].strftime('%Y-%m-%d'),
                                   'symbol': str(symbol), 'side': 'BUY' if notionals[j] > 0 else 'SELL',
                                   'notional': float(abs(notionals[j])), 'cost': float(abs(notionals[j]) * rate)})
            weights = target.copy()
        else:
            weights = drift
        new_nav = before - fee
        records.append({'date': day.strftime('%Y-%m-%d'), 'equity': new_nav,
                        'return': new_nav / nav - 1, 'turnover': turnover, 'cost': fee,
                        'exposure': float(weights.sum()),
                        'start_weights': beginning.tolist(), 'end_weights': weights.tolist()})
        nav = new_nav
    return records, trades


def run_engine(prices, request, strategy, execution_delay=1):
    req = ResearchRequest.model_validate(request)
    asset_prices = prices[req.symbols]
    targets, warmup = target_weights(asset_prices, strategy, req.lookback, req.fast_window, req.slow_window)
    if len(prices) - warmup - execution_delay < 60:
        raise ValueError('Not enough observations after warm-up. Extend the date range or reduce lookback/slow window.')
    due = decision_schedule(prices.index, req.rebalance, warmup)
    if strategy == 'buy_hold':
        due.iloc[:] = False
        due.iloc[warmup] = True
    total_bps = req.commission_bps + req.slippage_bps
    rows, trades = simulate(asset_prices, targets, due, execution_delay, req.initial_capital, total_bps)
    bench_prices = prices[[req.benchmark]]
    bench_target = pd.DataFrame(1.0, index=prices.index, columns=[req.benchmark])
    bench_due = pd.Series(False, index=prices.index)
    bench_due.iloc[warmup] = True
    benchmark, benchmark_trades = simulate(bench_prices, bench_target, bench_due, execution_delay, req.initial_capital, total_bps)
    baseline_index = warmup + execution_delay - 1
    start = baseline_index + 1
    curve = []
    for i in range(baseline_index, len(rows)):
        row = dict(rows[i]); row['benchmark_equity'] = benchmark[i]['equity']
        row['benchmark_return'] = benchmark[i]['return']
        curve.append(row)
    r = pd.Series([x['return'] for x in rows[start:]], index=prices.index[start:])
    b = pd.Series([x['return'] for x in benchmark[start:]], index=r.index)
    cut = max(1, int(len(r) * (1 - req.holdout_fraction)))
    baseline = prices.index[baseline_index]
    rf = req.annual_risk_free_rate
    metrics = {
        'strategy': performance(r, rf, baseline), 'benchmark': performance(b, rf, baseline),
        'development': performance(r.iloc[:cut], rf, baseline),
        'holdout': performance(r.iloc[cut:], rf, r.index[cut-1]),
        'holdout_benchmark': performance(b.iloc[cut:], rf, b.index[cut-1])}
    return sanitise({'strategy': strategy, 'request': req.model_dump(mode='json'), 'execution_delay': execution_delay,
        'warmup_observations': warmup, 'baseline_date': baseline.strftime('%Y-%m-%d'),
        'evaluation_start': r.index[0].strftime('%Y-%m-%d'), 'evaluation_end': r.index[-1].strftime('%Y-%m-%d'),
        'holdout_start': r.index[cut].strftime('%Y-%m-%d'),
        'metrics': metrics, 'curve': curve, 'trades': trades, 'benchmark_trades': benchmark_trades,
        'total_cost': float(sum(x['cost'] for x in rows)), 'trade_count': len(trades),
        'total_turnover': float(sum(x['turnover'] for x in rows)),
        'assumptions': ['Long-only; maximum total risky weight 100%; inactive allocations stay in zero-return cash.',
            'Decision at close t; execution at close t+delay; first asset return after that execution.',
            'Fractional units, no borrow/leverage/tax/capacity model, linear commission and slippage.',
            'Positions drift between rebalances; costs reduce capital; terminal positions marked to market, not liquidated.',
            'Benchmark enters on the same initial execution date and pays the same entry cost model.',
            'Chronological holdout uses fixed parameters and continuous positions; no parameter fitting or optimisation.',
            'Daily risk metrics use 252 trading observations per year; CAGR uses elapsed calendar time.']})
