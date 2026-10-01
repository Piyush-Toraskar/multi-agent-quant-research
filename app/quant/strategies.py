import pandas as pd


def target_weights(prices, strategy, lookback=60, fast_window=20, slow_window=80):
    if strategy == 'momentum':
        signal = prices / prices.shift(lookback) - 1 > 0
        warmup = lookback
    elif strategy == 'sma_cross':
        signal = prices.rolling(fast_window, min_periods=fast_window).mean() > prices.rolling(slow_window, min_periods=slow_window).mean()
        warmup = slow_window - 1
    elif strategy == 'buy_hold':
        signal = pd.DataFrame(True, index=prices.index, columns=prices.columns)
        warmup = 0
    else:
        raise ValueError('Unsupported strategy: ' + str(strategy))
    weights = signal.astype(float) / len(prices.columns)
    weights.iloc[:warmup] = 0.0
    return weights, warmup


def decision_schedule(index, frequency, warmup):
    due = pd.Series(False, index=index)
    if frequency == 'daily':
        due.iloc[warmup:] = True
    else:
        # First observed session in a new week/month: known without observing the future.
        periods = index.to_period('W' if frequency == 'weekly' else 'M')
        for i in range(warmup, len(index)):
            if i == warmup or periods[i] != periods[i-1]:
                due.iloc[i] = True
    return due
