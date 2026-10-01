import numpy as np
from app.storage import load_blob
from app.tools.market_data import load_dataset
from app.quant.backtest import run_engine


def verify_research(settings, artifact_id, dataset_id):
    result = load_blob(settings.data_dir / 'artifacts', artifact_id)
    prices, _ = load_dataset(settings, dataset_id)
    checks = []
    def check(name, passed, detail):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
    check('snapshot_link', result['dataset_id'] == dataset_id, 'Backtest references the exact immutable data snapshot.')
    check('execution_delay', result['execution_delay'] >= 1, 'A closing-price signal cannot trade at the same close.')
    check('trade_chronology', all(x['date'] > x['signal_date'] for x in result['trades']), 'Every trade follows its signal date.')
    check('costs_non_negative', result['total_cost'] >= 0, 'Trading costs never increase NAV.')
    check('positive_equity', all(x['equity'] > 0 for x in result['curve']), 'Equity stays strictly positive.')
    check('weights', all(min(x['end_weights']) >= -1e-9 and sum(x['end_weights']) <= 1+1e-9 for x in result['curve']), 'No shorting or leverage.')
    check('holdout_size', result['metrics']['holdout']['observations'] >= 15, 'At least 15 chronological holdout observations.')
    # Future perturbation should not affect any earlier portfolio decision or return.
    split = len(prices) * 2 // 3
    shocked = prices.copy()
    shocked.iloc[split:] = shocked.iloc[split:] * 1.7
    rerun = run_engine(shocked, result['request'], result['strategy'], result['execution_delay'])
    cutoff = prices.index[split].strftime('%Y-%m-%d')
    before = [row['equity'] for row in result['curve'] if row['date'] < cutoff]
    after = [row['equity'] for row in rerun['curve'] if row['date'] < cutoff]
    invariant = len(before) == len(after) and np.allclose(before, after, rtol=1e-12, atol=1e-8)
    check('future_perturbation', invariant, 'Changing only future prices leaves all earlier equity values unchanged.')
    failed = [x['name'] for x in checks if not x['passed']]
    return {'passed': not failed, 'checks': checks, 'failed': failed,
            'revision': 'increase_execution_delay' if failed and set(failed) <= {'execution_delay', 'trade_chronology', 'future_perturbation'} else None,
            'caveat': 'Engineering checks, not proof of absence of all bias or evidence of investment profitability.'}
