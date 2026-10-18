"""Persist causal counterexamples and audit corrected fills for review."""
import argparse
import json
import gzip
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import review_cross_market_clock as clock
import review_frozen_strategies as prior
from xquant.research_execution_clock import PriceBook, stamp, rebalance_group
from portfolio_strategies.market_data import PortfolioMarketData


def synthetic(dates):return pd.DataFrame({c:100. for c in ['Open','High','Low','Close']},index=dates)


def main(out):
    days=pd.bdate_range('2026-09-07',periods=6);config=prior.get_strategy('btc_supertrend_satellite')
    targets={days[1]:{'510300.SS':.925,'BTC-USD':.075},days[3]:{'510300.SS':.8,'BTC-USD':.075,'CASH':.125}}
    btc=[];us=[]
    for shock in [100.,200.]:
        frames={s:synthetic(days) for s in config.symbols};frames['BTC-USD'].loc[days[4]:,'Close']=shock
        close=pd.DataFrame({s:f.Close for s,f in frames.items()});market=PortfolioMarketData(close,close,close,close,days,days[-1].date(),())
        nav,_,_=clock.btc_replay(config,market,frames,targets);row=nav.loc[days[4]]
        btc.append({'later_btc_close':shock,'earlier_etf_quantity':float(row.nav*row['weight_510300.SS']/100.)})
        dates=pd.to_datetime(['2026-08-31','2026-09-01']);frames={'510300.SS':synthetic(dates),'SPY':synthetic(dates)};frames['SPY'].loc[dates[1],'Open']=shock
        book=PriceBook(frames);state={'cash':0.,'shares':{'510300.SS':1.,'SPY':1.},'costPaid':0.}
        rebalance_group(state,{'510300.SS':.5,'SPY':.5},book,stamp('510300.SS',dates[1],'Open'),{'510300.SS':100.},0.,0.,'__CASH__')
        us.append({'later_us_open':shock,'earlier_china_quantity':state['shares']['510300.SS']})
    assert btc[0]['earlier_etf_quantity']==btc[1]['earlier_etf_quantity']
    assert us[0]['earlier_china_quantity']==us[1]['earlier_china_quantity']
    prior.dump(out/'corrected-probes.json',{'btc_execution':btc,'multi_asset_execution':us,'scope':'Fixed synthetic targets; concrete causal counterexamples, not performance proof.'})
    audit=[]
    for path in (out/'btc').glob('fills_*.json'):
        fills=json.loads(path.read_text())
        violations=sum(pd.Timestamp(t)>pd.Timestamp(f['executionAt']) for f in fills for t in f['pricesKnownAt'].values())
        early=sum(pd.Timestamp(f['executionAt'])<=clock.available_signal(f['signal_date'],config.symbols) for f in fills)
        audit.append({'file':path.name,'future_price_clocks':violations,'execution_before_signal':early,
                      'max_cash_error':max(f['cashError'] for f in fills),'max_nav_error':max(f['navError'] for f in fills),
                      'max_quantity_error':max(f['quantityError'] for f in fills),
                      'unfilled_target_amount_sum':sum(sum(f['unfilledDesiredValues'].values()) for f in fills)})
        assert violations==early==0
    prior.dump(out/'btc_full_clock_audit.json',audit)
    multi_path=out/'multi_asset_full.json.gz'
    if multi_path.exists():
        with gzip.open(multi_path,'rt') as stream: multi=json.load(stream)
        audit=[]
        for row in multi['variants']+multi['benchmarks']:
            if row['id']=='existing_global_rs_monthly_macd': continue
            groups=[(order,f) for order in row.get('rebalances',[]) for f in order.get('clockAudit',[])]
            if not groups: continue
            future=sum(pd.Timestamp(t)>pd.Timestamp(f['executionAt']) for order,f in groups for t in f['pricesKnownAt'].values())
            early=sum(pd.Timestamp(f['executionAt'])<=pd.Timestamp(order['signalAvailableAt']) for order,f in groups)
            assert future==early==0
            audit.append({'strategy':row['id'],'groups':len(groups),'future_price_clocks':future,'execution_before_signal':early,
                          'max_cash_error':max(f['cashError'] for order,f in groups),'max_nav_error':max(f['navError'] for order,f in groups),
                          'max_quantity_error':max(f['quantityError'] for order,f in groups)})
        assert len(multi['variants'])==96 and len(multi['staticWeightStability']['points'])==85
        prior.dump(out/'multi_full_clock_audit.json',{'variants':96,'static_grid_points':85,'saved_fill_audits':audit,
                   'scope':'Saved candidate and baseline fills; grid fills checked at runtime but not individually retained. FX timing remains a model assumption.'})
    print('Saved corrected causal probes and BTC fill-clock audit')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'outputs/strategy-healthcheck-clock-correction-2026-10-03');args=p.parse_args();main(args.output)
