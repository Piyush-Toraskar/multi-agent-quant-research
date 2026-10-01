import pytest
from pydantic import ValidationError
from app.schemas import ResearchRequest, BacktestArgs


def test_defaults_are_valid():
    assert ResearchRequest().symbols == ['AAPL','MSFT']


def test_symbols_are_normalised():
    assert ResearchRequest(symbols='aapl, MSFT, AAPL').symbols == ['AAPL','MSFT']

@pytest.mark.parametrize('fields', [
    {'start':'2025-01-01','end':'2021-01-01'}, {'start':'2024-01-01','end':'2024-02-01'},
    {'symbols':['../../secrets']}, {'symbols':[]}, {'symbols':['=CMD()']}, {'symbols':['AAPL;DROP TABLE prices']},
    {'fast_window':50,'slow_window':30}, {'commission_bps':-1}, {'slippage_bps':float('nan')},
    {'holdout_fraction':0.01}, {'lookback':0}, {'initial_capital':-1}, {'strategy':'magic'},
    {'arbitrary_code':'print(1)'}, {'snapshot_id':'../data'}, {'query':'x'}])
def test_invalid_requests(fields):
    with pytest.raises(ValidationError):
        ResearchRequest(**fields)


def test_execution_delay_cannot_be_zero(request_data):
    with pytest.raises(ValidationError):
        BacktestArgs(dataset_id='a'*64, request=request_data, strategy='momentum', execution_delay=0)
