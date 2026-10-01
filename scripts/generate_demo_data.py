"""Generate deterministic, intentionally synthetic data. No market data is redistributed."""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd


def generate(path):
    index = pd.bdate_range('2018-01-01', '2025-12-31')
    market = np.random.default_rng(7301).normal(0.00025, 0.008, len(index))
    frame = pd.DataFrame(index=index)
    for ticker, base, beta in [('AAPL',80,1.1), ('MSFT',100,0.95), ('NVDA',50,1.4), ('JPM',90,0.9), ('SPY',200,1.0), ('QQQ',150,1.15)]:
        seed = int(hashlib.sha256(ticker.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        noise = rng.normal(0, 0.006 if ticker not in ['SPY','QQQ'] else 0.002, len(index))
        returns = beta * market + noise
        frame[ticker] = base * np.exp(np.cumsum(returns))
    frame.index.name = 'date'
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, float_format='%.10f')
    return frame

if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'data' / 'fixtures' / 'demo_prices.csv'
    data = generate(path)
    print(f'Wrote {len(data)} synthetic weekday observations to {path}')
