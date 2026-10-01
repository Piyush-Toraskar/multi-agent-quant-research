import numpy as np
import pandas as pd
import pytest
from app.quant.metrics import performance, beta
from app.quant.backtest import simulate, run_engine
from app.quant.strategies import target_weights, decision_schedule
from app.tools.market_data import load_dataset
from app.tools.quant_tools import run_backtest, assess_risk, analyse_market
from app.tools.verification import verify_research


def series(values):
    return pd.Series(values,index=pd.date_range('2021-01-02',periods=len(values)))


def test_returns_compound_not_sum():
    m=performance(series([.1,-.1]),baseline_date='2021-01-01')
    assert m['total_return']==pytest.approx(-.01)
    assert m['max_drawdown']==pytest.approx(-.1)


def test_first_day_loss_in_drawdown():
    assert performance(series([-.2,.1]),baseline_date='2021-01-01')['max_drawdown']==pytest.approx(-.2)


def test_zero_vol_sharpe_none():
    assert performance(series([0,0,0]))['sharpe'] is None


def test_beta_identity():
    assert beta([1,2,3],[1,2,3])==pytest.approx(1)
    assert beta([1,2,3],[1,1,1]) is None


def test_var_tail_loss_nonnegative():
    m=performance(series([-.1,-.01,.02,.03]))
    assert m['historical_cvar_95']>=m['historical_var_95']>=0


def test_sharpe_formula():
    vals=np.array([.01,-.02,.03,.005])
    assert performance(series(vals))['sharpe']==pytest.approx(vals.mean()/vals.std(ddof=1)*np.sqrt(252))


def test_sma_needs_warmup():
    p=pd.DataFrame({'A':range(1,12)},index=pd.date_range('2020-01-01',periods=11))
    w,warm=target_weights(p,'sma_cross',fast_window=2,slow_window=5)
    assert warm==4 and w.iloc[:4].sum().sum()==0 and w.iloc[4,0]==1


def test_no_same_close_return():
    index=pd.date_range('2021-01-01',periods=4)
    prices=pd.DataFrame({'A':[100,200,400,800]},index=index)
    target=pd.DataFrame(1.0,index=index,columns=['A'])
    due=pd.Series([True,False,False,False],index=index)
    rows,trades=simulate(prices,target,due,1,1000,0)
    assert [r['equity'] for r in rows]==pytest.approx([1000,1000,2000,4000])
    assert trades[0]['signal_date']=='2021-01-01' and trades[0]['date']=='2021-01-02'


def test_entry_cost_self_financing():
    index=pd.date_range('2021-01-01',periods=3)
    prices=pd.DataFrame({'A':[100,100,100]},index=index)
    targets=pd.DataFrame(1.,index=index,columns=['A']);due=pd.Series([True,False,False],index=index)
    rows,trades=simulate(prices,targets,due,1,1000,100)
    assert rows[-1]['equity']==pytest.approx(1000/1.01)
    assert sum(t['cost'] for t in trades)==pytest.approx(1000-1000/1.01)


def test_weights_drift_between_rebalances():
    index=pd.date_range('2021-01-01',periods=4)
    prices=pd.DataFrame({'A':[100,100,200,200],'B':[100,100,100,100]},index=index)
    target=pd.DataFrame(.5,index=index,columns=prices.columns);due=pd.Series([True,False,False,False],index=index)
    rows,_=simulate(prices,target,due,1,1000,0)
    assert rows[2]['end_weights']==pytest.approx([2/3,1/3])
    assert rows[2]['equity']==pytest.approx(1500)


def test_future_values_do_not_change_past(settings,request_data,dataset):
    prices,_=load_dataset(settings,dataset['dataset_id'])
    one=run_engine(prices,request_data,'momentum')
    split=len(prices)//2;changed=prices.copy();changed.iloc[split:]*=2
    two=run_engine(changed,request_data,'momentum')
    cutoff=prices.index[split].strftime('%Y-%m-%d')
    a=[r['equity'] for r in one['curve'] if r['date']<cutoff]
    b=[r['equity'] for r in two['curve'] if r['date']<cutoff]
    assert a==pytest.approx(b)

@pytest.mark.parametrize('strategy',['momentum','sma_cross','buy_hold'])
def test_all_strategies_and_critic(settings,request_data,dataset,strategy):
    result=run_backtest(settings,dataset['dataset_id'],request_data,strategy)
    assert result['metrics']['holdout']['observations']>=15
    assert result['metrics']['strategy']['max_drawdown']<=0
    assert all(assess_risk(settings,result['artifact_id'])['checks'].values())
    assert verify_research(settings,result['artifact_id'],dataset['dataset_id'])['passed']


def test_zero_cost_strategy_equals_benchmark_for_same_asset(settings,request_data,dataset):
    prices,_=load_dataset(settings,dataset['dataset_id'])
    req=dict(request_data,symbols=['SPY'],benchmark='SPY',commission_bps=0,slippage_bps=0)
    result=run_engine(prices,req,'buy_hold')
    assert result['metrics']['strategy']==result['metrics']['benchmark']


def test_costs_reduce_wealth(settings,request_data,dataset):
    prices,_=load_dataset(settings,dataset['dataset_id'])
    free=run_engine(prices,dict(request_data,commission_bps=0,slippage_bps=0),'momentum')
    paid=run_engine(prices,dict(request_data,commission_bps=50,slippage_bps=50),'momentum')
    assert paid['curve'][-1]['equity']<free['curve'][-1]['equity']


def test_buy_hold_only_enters_once_per_asset(settings,request_data,dataset):
    prices,_=load_dataset(settings,dataset['dataset_id'])
    result=run_engine(prices,request_data,'buy_hold')
    assert result['trade_count']==len(request_data['symbols'])


def test_insufficient_warmup_data(settings,request_data,dataset):
    prices,_=load_dataset(settings,dataset['dataset_id'])
    with pytest.raises(ValueError,match='Not enough'):
        run_engine(prices.iloc[:100],request_data,'sma_cross')


def test_correlations_are_symmetric(settings,dataset):
    result=analyse_market(settings,dataset['dataset_id'])['correlation']
    assert result['AAPL']['MSFT']==pytest.approx(result['MSFT']['AAPL'])
    assert result['AAPL']['AAPL']==pytest.approx(1)


def test_month_schedule_has_no_future_dependency():
    index=pd.bdate_range('2021-01-01',periods=80)
    full=decision_schedule(index,'monthly',5)
    short=decision_schedule(index[:40],'monthly',5)
    pd.testing.assert_series_equal(full.iloc[:40],short)



def test_nonfinite_targets_rejected():
    index=pd.date_range('2021-01-01',periods=3)
    prices=pd.DataFrame({'A':[100,100,100]},index=index)
    targets=pd.DataFrame({'A':[1,float('nan'),1]},index=index)
    with pytest.raises(ValueError,match='finite'):
        simulate(prices,targets,pd.Series(True,index=index),1,1000,10)


def test_cost_ledger_reconciles(settings,request_data,dataset):
    prices,_=load_dataset(settings,dataset['dataset_id'])
    result=run_engine(prices,dict(request_data,rebalance='daily'),'momentum')
    assert sum(x['cost'] for x in result['trades'])==pytest.approx(result['total_cost'],rel=1e-10)
    assert sum(x['cost'] for x in result['curve'])==pytest.approx(result['total_cost'],rel=1e-10)


def test_positions_never_exceed_capital(settings,request_data,dataset):
    prices,_=load_dataset(settings,dataset['dataset_id'])
    result=run_engine(prices,request_data,'sma_cross')
    for row in result['curve']:
        assert min(row['start_weights'])>=0
        assert sum(row['start_weights'])<=1+1e-9
        assert row['cost']>=0
