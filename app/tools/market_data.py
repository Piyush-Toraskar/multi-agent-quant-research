"""Synthetic fixtures are never substituted for a failed real-data request."""
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from app.config import ROOT
from app.schemas import ResearchRequest
from app.storage import load_blob, save_blob


def validate_prices(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError('No price data returned for this date range')
    frame = frame.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index)).tz_localize(None)
    if frame.index.has_duplicates:
        raise ValueError('Duplicate dates in price data')
    if not frame.index.is_monotonic_increasing:
        raise ValueError('Price dates must be increasing')
    frame = frame.astype(float)
    values = frame.to_numpy()
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('Prices must be finite, non-missing and strictly positive')
    return frame


def load_dataset(settings, identifier):
    payload = load_blob(settings.data_dir / 'snapshots', identifier)
    frame = pd.DataFrame(payload['prices'], index=pd.to_datetime(payload['dates']))
    return validate_prices(frame), payload['metadata']


def fetch_prices(settings, request: dict) -> dict:
    req = ResearchRequest.model_validate(request)
    symbols = list(dict.fromkeys(req.symbols + [req.benchmark]))
    if req.snapshot_id:
        frame, metadata = load_dataset(settings, req.snapshot_id)
        for key, value in {'provider': req.provider, 'symbols': symbols, 'start': str(req.start), 'end': str(req.end), 'benchmark': req.benchmark, 'strategy_symbols': req.symbols}.items():
            if metadata.get(key) != value:
                raise ValueError('Replay snapshot does not match requested ' + key)
        identifier = req.snapshot_id
    else:
        if req.provider == 'demo':
            raw = pd.read_csv(ROOT / 'data' / 'fixtures' / 'demo_prices.csv', index_col='date', parse_dates=True)
            unknown = sorted(set(symbols) - set(raw.columns))
            if unknown:
                raise ValueError('Demo symbols are AAPL, MSFT, NVDA, JPM, SPY and QQQ; unknown: ' + ', '.join(unknown))
            if req.start < raw.index[0].date() or req.end > (raw.index[-1] + pd.Timedelta(days=1)).date():
                raise ValueError('Demo data covers 2018-01-01 through 2025-12-31; end is exclusive (maximum 2026-01-01).')
            raw = raw.loc[(raw.index >= str(req.start)) & (raw.index < str(req.end)), symbols]
            source = 'Deterministic synthetic fixture; NOT historical market prices'
        else:
            try:
                import yfinance as yf
            except ImportError as exc:
                raise RuntimeError('Live data requires yfinance. Run python -m pip install yfinance.') from exc
            series = []
            for symbol in symbols:
                item = yf.download(symbol, start=str(req.start), end=str(req.end), auto_adjust=True,
                                   progress=False, threads=False, timeout=20)
                if item is None or item.empty:
                    raise ValueError('No Yahoo Finance data for ' + symbol + '; check the ticker, dates and rate limits')
                if isinstance(item.columns, pd.MultiIndex):
                    close = item['Close'].iloc[:, 0]
                else:
                    close = item['Close']
                series.append(close.rename(symbol))
            raw = pd.concat(series, axis=1).sort_index()
            source = 'Yahoo Finance via yfinance; adjusted Close (provider-supplied adjustments)'
        rows_before = len(raw)
        # Align all assets and benchmark to common observed dates; never forward-fill prices.
        frame = validate_prices(raw.dropna(how='any'))
        if len(frame) < 80:
            raise ValueError('Fewer than 80 common price observations; use a longer date range')
        warnings = ['Fixed, user-chosen universe: no point-in-time index membership or delisted-stock coverage.',
                    'Daily adjusted closes only; no intraday fills, order book or FX conversion.',
                    'Cash earns zero; risk-free rate is only a Sharpe/Sortino hurdle.']
        if req.provider == 'demo':
            warnings += ['SYNTHETIC DATA: results demonstrate software, not a real investment opportunity.',
                         'Demo calendar is weekdays, not an exchange holiday calendar.']
        else:
            warnings += ['All symbols must use the same currency and a comparable trading session; this is not automatically verified.',
                         'Provider adjustments may be revised; retain this immutable snapshot for reproduction.']
        if rows_before != len(frame):
            warnings.append(f'Dropped {rows_before - len(frame)} non-common/missing dates; did not fill gaps.')
        metadata = {'provider': req.provider, 'source': source, 'symbols': symbols,
                    'start': str(req.start), 'end': str(req.end), 'benchmark': req.benchmark,
                    'strategy_symbols': req.symbols, 'rows': len(frame), 'dropped_rows': rows_before - len(frame),
                    'retrieved_at': ('synthetic-fixture-v1' if req.provider == 'demo' else datetime.now(timezone.utc).isoformat()),
                    'warnings': warnings}
        identifier = save_blob(settings.data_dir / 'snapshots', {
            'dates': frame.index.strftime('%Y-%m-%d').tolist(),
            'prices': {str(c): frame[c].tolist() for c in frame}, 'metadata': metadata})
    return {'dataset_id': identifier, 'metadata': metadata,
            'first_date': frame.index[0].strftime('%Y-%m-%d'), 'last_date': frame.index[-1].strftime('%Y-%m-%d')}
