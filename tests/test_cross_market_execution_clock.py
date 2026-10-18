"""Causal probes: a later market cannot alter an earlier fill or fund it."""
import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from xquant.research_execution_clock import PriceBook, stamp, rebalance_group
import review_cross_market_clock as corrected
import review_frozen_strategies as prior
from portfolio_strategies.market_data import PortfolioMarketData


def frame(dates,price=100.):
    return pd.DataFrame({c:price for c in ('Open','High','Low','Close')},index=dates)


def test_later_btc_close_cannot_change_earlier_etf_fill():
    config=prior.get_strategy('btc_supertrend_satellite')
    days=pd.bdate_range('2026-09-07',periods=6)
    targets={days[1]:{'510300.SS':.925,'BTC-USD':.075},days[3]:{'510300.SS':.8,'BTC-USD':.075,'CASH':.125}}
    quantities=[]
    for shock in (100.,200.):
        frames={s:frame(days) for s in config.symbols}
        frames['BTC-USD'].loc[days[4]:,'Close']=shock
        close=pd.DataFrame({s:f.Close for s,f in frames.items()})
        market=PortfolioMarketData(close,close,close,close,days,days[-1].date(),())
        nav,_,audit=corrected.btc_replay(config,market,frames,targets)
        row=nav.loc[days[4]]
        quantities.append(row.nav*row['weight_510300.SS']/100.)
        assert all(pd.Timestamp(t)<=pd.Timestamp(a['executionAt']) for a in audit for t in a['pricesKnownAt'].values())
    assert quantities[0]==pytest.approx(quantities[1])


def test_later_us_open_cannot_change_china_fill_or_precredit_proceeds():
    days=pd.to_datetime(['2026-08-31','2026-09-01'])
    quantities=[]
    for shock in (100.,200.):
        frames={'510300.SS':frame(days),'SPY':frame(days)}
        frames['SPY'].loc[days[1],'Open']=shock
        book=PriceBook(frames)
        state={'cash':0.,'shares':{'510300.SS':1.,'SPY':1.},'costPaid':0.}
        early=stamp('510300.SS',days[1],'Open')
        rebalance_group(state,{'510300.SS':.5,'SPY':.5},book,early,{'510300.SS':100.},0.,0.,'__CASH__')
        quantities.append(state['shares']['510300.SS'])
        # Zero cash and SPY hasn't sold yet: China cannot buy another share.
        state={'cash':0.,'shares':{'SPY':2.},'costPaid':0.}
        result=rebalance_group(state,{'510300.SS':1.},book,early,{'510300.SS':100.},0.,0.,'__CASH__')
        assert state['shares'].get('510300.SS',0.)==0.
        assert result['cashAfter']==0.
        late=stamp('SPY',days[1],'Open')
        rebalance_group(state,{'510300.SS':1.},book,late,{'SPY':shock},0.,0.,'__CASH__')
        assert state['cash']>0.
    assert quantities[0]==pytest.approx(quantities[1])


def test_us_clock_tracks_dst_and_half_day_close():
    assert stamp('SPY','2026-07-01','Open')==pd.Timestamp('2026-07-01 13:30Z')
    assert stamp('SPY','2026-01-02','Open')==pd.Timestamp('2026-01-02 14:30Z')
    assert stamp('SPY','2026-11-27','Close')==pd.Timestamp('2026-11-27 18:00Z')


def test_btc_signal_after_bar_close_uses_next_real_utc_close():
    days=pd.date_range('2026-09-21',periods=4)
    book=PriceBook({'BTC-USD':frame(days)})
    ready=pd.Timestamp('2026-09-23 00:00:01Z')
    at,label,_=book.next_quote('BTC-USD',ready,'Close')
    assert label==pd.Timestamp('2026-09-23')
    assert at==pd.Timestamp('2026-09-24 00:00Z')


def test_fx_at_open_uses_completed_prior_fx_and_one_factor_per_bar():
    days=pd.date_range('2026-09-20',periods=5)
    asset=frame(days);fx=frame(days,7.)
    fx.loc[days[2]:,'Close']=100.
    converted=corrected.fx_at_open(asset,'BTC-USD',fx)
    assert converted.loc[days[2],'Open']==700.
    assert converted.loc[days[2],'High']==700.
    assert converted.loc[days[2],'Close']==700.
    assert converted.loc[days[4],'Open']==10000.


def test_group_fees_cash_conserve_and_insufficient_buy_scales():
    days=pd.to_datetime(['2026-08-31','2026-09-01'])
    book=PriceBook({'510300.SS':frame(days),'SPY':frame(days)})
    state={'cash':10.,'shares':{'SPY':1.},'costPaid':0.}
    result=rebalance_group(state,{'510300.SS':.9,'SPY':.1},book,stamp('510300.SS',days[1],'Open'),{'510300.SS':100.},5.,5.,'__CASH__')
    assert 0.<state['shares']['510300.SS']<.1
    assert state['cash']==pytest.approx(0.)
    assert result['cashError']<1e-10
    assert state['costPaid']>0.


def test_actual_multi_scheduler_does_not_use_later_open_for_earlier_order():
    path=ROOT.parent/'trading/scripts/research_multi_asset_balanced_portfolio.py'
    spec=importlib.util.spec_from_file_location('clock_multi_probe',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    days=pd.bdate_range('2026-07-30','2026-09-03')
    quantities=[]
    for shock in (100.,200.):
        frames={'510300.SS':frame(days),'SPY':frame(days)}
        frames['SPY'].loc['2026-09-01','Open']=shock
        def target(day):
            return ({'510300.SS':.5,'SPY':.5} if day.month==7 else {'510300.SS':.9,'SPY':.1}),{}
        result=corrected.corrected_monthly(module,frames,target,fee_bps=0.,slippage_bps=0.)
        trades=[t for order in result['rebalances'] for t in order['trades'] if t['symbol']=='510300.SS' and pd.Timestamp(t['executedAt'])<=stamp('510300.SS','2026-09-01','Open')]
        quantities.append(sum((1 if t['side']=='buy' else -1)*t['shares'] for t in trades))
        for order in result['rebalances']:
            assert all(pd.Timestamp(t['executedAt'])>pd.Timestamp(order['signalAvailableAt']) for t in order['trades'])
    assert quantities[0]==pytest.approx(quantities[1])
