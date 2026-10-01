from datetime import date
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class ResearchRequest(StrictModel):
    query: str = Field('Test momentum on AAPL and MSFT against SPY.', min_length=5, max_length=2500)
    symbols: list[str] = Field(default_factory=lambda: ['AAPL', 'MSFT'], min_length=1, max_length=8)
    benchmark: str = 'SPY'
    start: date = date(2021, 1, 1)
    end: date = date(2025, 1, 1)
    provider: Literal['demo', 'yfinance'] = 'demo'
    strategy: Literal['auto', 'momentum', 'sma_cross', 'buy_hold'] = 'auto'
    lookback: int = Field(60, ge=2, le=252)
    fast_window: int = Field(20, ge=2, le=200)
    slow_window: int = Field(80, ge=3, le=300)
    rebalance: Literal['daily', 'weekly', 'monthly'] = 'monthly'
    commission_bps: float = Field(5, ge=0, le=100)
    slippage_bps: float = Field(5, ge=0, le=100)
    initial_capital: float = Field(100000, ge=100, le=1e10)
    annual_risk_free_rate: float = Field(0.0, ge=0, le=0.25)
    holdout_fraction: float = Field(0.3, ge=0.2, le=0.5)
    snapshot_id: str | None = Field(None, pattern=r'^[a-f0-9]{64}$')

    @field_validator('symbols', mode='before')
    @classmethod
    def clean_symbols(cls, v):
        if isinstance(v, str):
            v = v.split(',')
        if not isinstance(v, list):
            raise ValueError('symbols must be a list or a comma-separated string')
        return list(dict.fromkeys(str(s).strip().upper() for s in v))

    @field_validator('benchmark', mode='before')
    @classmethod
    def clean_benchmark(cls, v):
        return str(v).strip().upper()

    @model_validator(mode='after')
    def check(self):
        for symbol in self.symbols + [self.benchmark]:
            if not re.fullmatch(r'[A-Z0-9^][A-Z0-9.^=-]{0,19}', symbol):
                raise ValueError('Invalid ticker. Use symbols such as AAPL or RELIANCE.NS.')
        if self.end <= self.start:
            raise ValueError('end must be after start; end is exclusive')
        if (self.end - self.start).days < 120:
            raise ValueError('Use at least 120 calendar days of data')
        if (self.end - self.start).days > 366 * 20:
            raise ValueError('Date range is limited to 20 years')
        if self.fast_window >= self.slow_window:
            raise ValueError('fast_window must be smaller than slow_window')
        return self

class Plan(StrictModel):
    strategy: Literal['momentum', 'sma_cross', 'buy_hold']
    hypothesis: str = Field(min_length=5, max_length=1200)
    rationale: str = Field(min_length=5, max_length=2000)

class FetchArgs(StrictModel):
    request: ResearchRequest

class AnalysisArgs(StrictModel):
    dataset_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    lookback: int = Field(60, ge=2, le=252)

class BacktestArgs(StrictModel):
    dataset_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    request: ResearchRequest
    strategy: Literal['momentum', 'sma_cross', 'buy_hold']
    # Decision at close t -> trade at close t+1 -> first return ending t+2.
    execution_delay: int = Field(1, ge=1, le=3)

class ArtifactArgs(StrictModel):
    artifact_id: str = Field(pattern=r'^[a-f0-9]{64}$')

class VerifyArgs(StrictModel):
    artifact_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    dataset_id: str = Field(pattern=r'^[a-f0-9]{64}$')

class SearchArgs(StrictModel):
    query: str = Field('', max_length=200)
    limit: int = Field(5, ge=1, le=20)

class GetRunArgs(StrictModel):
    run_id: str = Field(pattern=r'^[a-f0-9]{32}$')
