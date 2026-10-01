from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from app.tools.market_data import fetch_prices, load_dataset, validate_prices
from app.storage import save_blob, load_blob


def test_demo_is_labelled_and_deterministic(settings, request_data):
    a=fetch_prices(settings,request_data);b=fetch_prices(settings,request_data)
    assert a['dataset_id']==b['dataset_id']
    assert 'NOT historical' in a['metadata']['source']
    frame, metadata=load_dataset(settings,a['dataset_id'])
    assert frame.index[-1] < pd.Timestamp(request_data['end'])
    assert set(frame)=={'AAPL','MSFT','SPY'}
    assert np.isfinite(frame.to_numpy()).all()


def test_overlapping_slices_identical(settings, request_data):
    a=fetch_prices(settings, request_data)
    b=fetch_prices(settings, dict(request_data,start='2022-01-01'))
    full,_=load_dataset(settings,a['dataset_id']);part,_=load_dataset(settings,b['dataset_id'])
    pd.testing.assert_frame_equal(full.loc[part.index],part)


def test_unknown_demo_symbol_is_error(settings, request_data):
    with pytest.raises(ValueError,match='unknown'):
        fetch_prices(settings,dict(request_data,symbols=['NOTREAL']))


def test_outside_demo_dates_is_error(settings, request_data):
    with pytest.raises(ValueError,match='covers'):
        fetch_prices(settings,dict(request_data,start='2010-01-01'))


def test_snapshot_replay(settings, request_data, dataset):
    replay=fetch_prices(settings,dict(request_data,snapshot_id=dataset['dataset_id']))
    assert replay['dataset_id']==dataset['dataset_id']


def test_snapshot_replay_mismatch(settings, request_data, dataset):
    with pytest.raises(ValueError,match='match'):
        fetch_prices(settings,dict(request_data,snapshot_id=dataset['dataset_id'],start='2022-01-01'))

@pytest.mark.parametrize('values', [[100,0,110],[100,-1,110],[100,float('nan'),110],[100,float('inf'),110]])
def test_bad_prices_rejected(values):
    with pytest.raises(ValueError):
        validate_prices(pd.DataFrame({'A':values},index=pd.date_range('2020-01-01',periods=3)))


def test_duplicate_dates_rejected():
    with pytest.raises(ValueError,match='Duplicate'):
        validate_prices(pd.DataFrame({'A':[1,2]},index=['2020-01-01','2020-01-01']))


def test_unordered_dates_rejected():
    with pytest.raises(ValueError,match='increasing'):
        validate_prices(pd.DataFrame({'A':[1,2]},index=['2020-01-02','2020-01-01']))


def test_empty_data_rejected():
    with pytest.raises(ValueError):
        validate_prices(pd.DataFrame())


def test_hash_integrity_and_traversal(tmp_path):
    identifier=save_blob(tmp_path,{'value':1})
    assert load_blob(tmp_path,identifier)=={'value':1}
    with pytest.raises(ValueError):
        load_blob(tmp_path,'../../secret')
    (tmp_path/(identifier+'.json')).write_text('{"value":2}')
    with pytest.raises(ValueError,match='integrity'):
        load_blob(tmp_path,identifier)



def test_live_provider_adapter_without_network(settings,request_data,monkeypatch):
    import sys
    from types import SimpleNamespace
    index=pd.bdate_range('2021-01-01','2024-12-31')
    calls=[]
    def download(ticker,**kwargs):
        calls.append((ticker,kwargs))
        assert kwargs['auto_adjust'] is True and kwargs['threads'] is False
        return pd.DataFrame({'Close':np.arange(len(index),dtype=float)+100},index=index)
    monkeypatch.setitem(sys.modules,'yfinance',SimpleNamespace(download=download))
    result=fetch_prices(settings,dict(request_data,provider='yfinance'))
    assert result['metadata']['provider']=='yfinance'
    assert len(calls)==3
    assert 'Yahoo Finance' in result['metadata']['source']
    assert all(call[1]['end']=='2025-01-01' for call in calls)


def test_live_feed_failure_never_falls_back(settings,request_data,monkeypatch):
    import sys
    from types import SimpleNamespace
    monkeypatch.setitem(sys.modules,'yfinance',SimpleNamespace(download=lambda *a,**k:pd.DataFrame()))
    with pytest.raises(ValueError,match='No Yahoo'):
        fetch_prices(settings,dict(request_data,provider='yfinance'))


def test_live_provider_multiindex(settings,request_data,monkeypatch):
    import sys
    from types import SimpleNamespace
    index=pd.bdate_range('2021-01-01','2024-12-31')
    def download(ticker,**kwargs):
        columns=pd.MultiIndex.from_tuples([('Close',ticker)])
        return pd.DataFrame(np.arange(len(index)).reshape(-1,1)+100,index=index,columns=columns)
    monkeypatch.setitem(sys.modules,'yfinance',SimpleNamespace(download=download))
    result=fetch_prices(settings,dict(request_data,provider='yfinance'))
    assert result['metadata']['rows']==len(index)
