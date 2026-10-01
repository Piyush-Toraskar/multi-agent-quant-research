import math
import numpy as np
import pandas as pd
from app.storage import sanitise

TRADING_DAYS = 252


def performance(returns: pd.Series, annual_risk_free_rate=0.0, baseline_date=None):
    values = returns.to_numpy(dtype=float)
    if len(values) == 0 or not np.isfinite(values).all() or (values <= -1).any():
        raise ValueError('Returns must be non-empty, finite and greater than -100%')
    growth = np.cumprod(1 + values)
    equity = np.r_[1.0, growth]
    drawdown = equity / np.maximum.accumulate(equity) - 1
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    daily_rf = math.expm1(math.log1p(annual_risk_free_rate) / TRADING_DAYS)
    excess = values - daily_rf
    downside = float(np.sqrt(np.mean(np.minimum(excess, 0) ** 2)))
    start = pd.Timestamp(baseline_date) if baseline_date is not None else returns.index[0]
    days = (returns.index[-1] - start).days
    years = days / 365.25
    cagr = float(np.expm1(np.log(growth[-1]) / years)) if years > 0 else None
    q05 = float(np.quantile(values, .05))
    tail = values[values <= q05]
    return sanitise({'total_return': float(growth[-1] - 1), 'cagr': cagr,
        'annualised_volatility': std * math.sqrt(TRADING_DAYS),
        'sharpe': float(np.mean(excess) / std * math.sqrt(TRADING_DAYS)) if std > 1e-12 else None,
        'sortino': float(np.mean(excess) / downside * math.sqrt(TRADING_DAYS)) if downside > 1e-12 else None,
        'max_drawdown': float(drawdown.min()), 'historical_var_95': max(0.0, -q05),
        'historical_cvar_95': max(0.0, -float(tail.mean())), 'positive_day_fraction': float((values > 0).mean()),
        'observations': len(values), 'calendar_days': days})


def beta(asset, benchmark):
    a, b = np.asarray(asset, float), np.asarray(benchmark, float)
    variance = float(np.var(b, ddof=1)) if len(b) > 1 else 0.0
    return float(np.cov(a, b, ddof=1)[0, 1] / variance) if variance > 1e-15 else None
