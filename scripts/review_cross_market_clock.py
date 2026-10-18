"""Isolated corrected-clock research; never changes production implementations."""
import argparse
from collections import defaultdict
from datetime import datetime
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT.parent/'trading/backend'))
from xquant.research_execution_clock import PriceBook, available_signal, stamp, rebalance_group
import review_frozen_strategies as prior


def btc_replay(config, market, frames, targets, extra_cost_bps=0):
    book=PriceBook(frames)
    state={'cash':config.initial_nav,'shares':{},'costPaid':0.}
    timeline=defaultdict(list)
    activation=market.sessions[market.sessions.get_loc(min(targets))-1]
    cutoff=stamp('510300.SS',market.sessions[-1],'Close')+pd.Timedelta(seconds=2)
    for day,target in targets.items():
        ready=available_signal(day,config.symbols)
        timeline[ready].append(('signal',(day,target)))
    for day in market.sessions[market.sessions>=activation]:
        timeline[stamp('510300.SS',day,'Close')+pd.Timedelta(seconds=2)].append(('nav',day))
    engine=prior.PortfolioPaperEngine.__new__(prior.PortfolioPaperEngine)
    events=[]; rows=[]; audit=[]
    import heapq
    queue=list(timeline);heapq.heapify(queue); processed=set()
    while queue:
        when=heapq.heappop(queue)
        if when>cutoff: break
        if when in processed: continue
        processed.add(when)
        for kind,data in timeline[when]:
            if kind=='signal':
                day,target=data
                gross,prices,_=book.mark(state,when)
                current={s:state['shares'].get(s,0.)*prices.get(s,0.)/gross for s in config.symbols}
                current['CASH']=state['cash']/gross
                execute,turnover=engine._should_execute(config,current,target)
                events.append({'signal_date':str(day.date()),'signal_available_at':str(when),'executed':execute,'turnover':turnover,'target':json.dumps(target)})
                if not execute: continue
                groups=defaultdict(dict)
                for s in config.symbols:
                    quote=book.next_quote(s,when,'Close')
                    if quote is not None:
                        at,label,p=quote; groups[at][s]=p
                for at,quotes in groups.items():
                    timeline[at].append(('fill',(day,target,quotes)))
                    heapq.heappush(queue,at)
            elif kind=='fill':
                day,target,quotes=data
                fill=rebalance_group(state,target,book,when,quotes,config.costs.base_bps+config.costs.slippage_bps+extra_cost_bps,0.,'CASH')
                fill['signal_date']=str(day.date()); audit.append(fill)
            else:
                gross,prices,_=book.mark(state,when)
                rows.append({'date':data,'valuation_at':str(when),'nav':gross,'cash_weight':state['cash']/gross,
                             **{f'weight_{s}':state['shares'].get(s,0.)*prices.get(s,0.)/gross for s in config.symbols}})
    nav=pd.DataFrame(rows).set_index('date')
    return nav,events,audit


def fx_at_open(frame,symbol,fx):
    """One known FX close held constant through a bar; accounting proxy only."""
    clocks=np.array([(pd.Timestamp(d).tz_localize('UTC')+pd.Timedelta(days=1,seconds=1)).value for d in fx.index],dtype=np.int64)
    opens=np.array([stamp(symbol,d,'Open').value for d in frame.index],dtype=np.int64)
    pos=np.searchsorted(clocks,opens,side='right')-1
    values=np.where(pos>=0,fx.Close.to_numpy()[np.maximum(pos,0)],np.nan)
    converted=frame.copy()
    for col in ('Open','High','Low','Close'):
        if col in converted: converted[col]*=values
    return converted


def run_btc(snapshot,out):
    dest=out/'btc';dest.mkdir(parents=True,exist_ok=False)
    config=prior.get_strategy('btc_supertrend_satellite')
    market=prior.load_market(config,snapshot,datetime(2026,10,2,16,tzinfo=ZoneInfo('Asia/Shanghai')),'2016-05-01')
    targets,observations=prior.btc_targets(config,market)
    frames={s:pd.read_parquet(snapshot/f'{s}.parquet').loc['2016-05-01':] for s in config.symbols}
    summaries=[];audits=[]
    windows={'full_common':'2016-06-07','2026_ytd':'2025-12-31','recent_3m':'2026-06-30','since_prior_review':'2026-08-10'}
    for label,target in targets.items():
        nav,events,audit=btc_replay(config,market,frames,target)
        nav.to_csv(dest/f'nav_{label}.csv');prior.dump(dest/f'events_{label}.json',events);prior.dump(dest/f'fills_{label}.json',audit)
        for period,start in windows.items():
            summaries.append({'strategy':label,'period':period,**prior.summarize(nav,start,market.sessions[-1])})
        audits.append({'strategy':label,'max_cash_error':max((r['cashError'] for r in audit),default=0.),'trade_groups':len(audit)})
        print('BTC complete',label,flush=True)
    sensitivity=[]
    for extra in (10,20):
        nav,_,_=btc_replay(config,market,frames,targets['BTC_7.5'],extra)
        nav.to_csv(dest/f'nav_BTC_7.5_extra{extra}bps.csv')
        sensitivity.append({'strategy':'BTC_7.5','extra_cost_bps':extra,**prior.summarize(nav,nav.index[0],nav.index[-1])})
    fx=pd.read_parquet(snapshot/'CNY=X.parquet')
    converted=dict(frames);converted['BTC-USD']=fx_at_open(frames['BTC-USD'],'BTC-USD',fx)
    nav,events,audit=btc_replay(config,market,converted,targets['BTC_7.5'])
    nav.to_csv(dest/'nav_BTC_7.5_fx_accounting.csv');prior.dump(dest/'fills_BTC_7.5_fx_accounting.json',audit)
    prior.dump(dest/'fx_diagnostic.json',{'assumption':'Known FX at BTC UTC bar open, held constant throughout that bar; frozen USD signals; accounting sensitivity without actual FX execution',
         'full':prior.summarize(nav,nav.index[0],nav.index[-1]),'recent_3m':prior.summarize(nav,'2026-06-30',nav.index[-1])})
    pd.DataFrame(summaries).to_csv(dest/'summary.csv',index=False);pd.DataFrame(sensitivity).to_csv(dest/'cost_sensitivity.csv',index=False)
    prior.dump(dest/'config.json',config);prior.dump(dest/'signals.json',observations);prior.dump(dest/'audit.json',audits)


def corrected_monthly(module,frames,target_weight_fn,start=None,end=None,fee_bps=5.,slippage_bps=5.,drift_threshold=0.,initial_cash=1.,simulation_cache=None):
    # Each monthly decision is available after all labels through month-end complete.
    book=PriceBook(frames)
    all_dates=list(simulation_cache['allDates']) if simulation_cache else sorted({d for f in frames.values() for d in f.index if (start is None or d>=pd.Timestamp(start)) and (end is None or d<=pd.Timestamp(end))})
    if not all_dates: return {'equityCurve':[],'rebalances':[],'costPaid':0.}
    timeline=defaultdict(list)
    last=all_dates[-1]
    # Valuation is after all closes for a daily label have become available.
    def valuation(day): return max(stamp(s,day,'Close') if day in f.index else pd.Timestamp(day).tz_localize('UTC') for s,f in frames.items())+pd.Timedelta(seconds=2)
    cutoff=valuation(last)
    months=pd.date_range(all_dates[0].to_period('M').end_time.normalize(),last.to_period('M').end_time.normalize(),freq='ME')
    for day in months:
        if day>=last:continue
        # Weekend signals wait for the UTC calendar day to finish, too.
        ready=max(pd.Timestamp(day).tz_localize('UTC')+pd.Timedelta(days=1,seconds=1),max((stamp(s,f.index[f.index<=day][-1],'Close')+pd.Timedelta(seconds=1)) for s,f in frames.items() if len(f.index[f.index<=day])))
        timeline[ready].append(('signal',day))
    for day in all_dates:timeline[valuation(day)].append(('nav',day))
    import heapq
    queue=list(timeline);heapq.heapify(queue);processed=set()
    state={'cash':initial_cash,'shares':{},'lastPrices':{},'costPaid':0.};curves=[];rebalances=[];peak=initial_cash
    while queue:
        when=heapq.heappop(queue)
        if when>cutoff:break
        if when in processed:continue
        processed.add(when)
        for kind,data in timeline[when]:
            if kind=='signal':
                target,diagnostics=target_weight_fn(data)
                nav,prices,_=book.mark(state,when)
                before={s:q*prices[s]/nav for s,q in state['shares'].items()};before['__CASH__']=state['cash']/nav
                if not module.should_trade(before,target,drift_threshold):continue
                symbols=set(state['shares'])|{s for s,w in target.items() if s!='__CASH__' and w>0}
                groups=defaultdict(dict)
                for s in symbols:
                    quote=book.next_quote(s,when,'Open')
                    if quote is not None:
                        at,label,p=quote;groups[at][s]=p
                order={'signalMonth':str(data.date()),'signalAvailableAt':str(when),'executionDate':None,'priorWeights':before,'targetWeights':target,'trades':[],'diagnostics':diagnostics,'cashErrors':[], 'clockAudit':[]}
                rebalances.append(order)
                for at,quotes in groups.items():
                    timeline[at].append(('fill',(target,quotes,order)));heapq.heappush(queue,at)
            elif kind=='fill':
                target,quotes,order=data
                fill=rebalance_group(state,target,book,when,quotes,fee_bps,slippage_bps,'__CASH__')
                order['executionDate']=str(when.date());order['trades'].extend(fill['trades']);order['cashErrors'].append(fill['cashError'])
                if pd.Timestamp(order['signalAvailableAt']) >= when:
                    raise AssertionError('Execution preceded signal availability')
                if any(pd.Timestamp(t)>when for t in fill['pricesKnownAt'].values()):
                    raise AssertionError('Future price entered execution')
                order['clockAudit'].append({k:v for k,v in fill.items() if k!='trades'})
            else:
                nav,prices,_=book.mark(state,when);peak=max(peak,nav)
                curves.append({'date':str(data.date()),'equity':nav,'drawdownPct':(peak-nav)/peak*100,'staleSymbols':[], 'valuationAt':str(when)})
    return {'equityCurve':curves,'rebalances':rebalances,'costPaid':state['costPaid'],'finalState':state}


def run_multi(snapshot,out):
    path=ROOT.parent/'trading/scripts/research_multi_asset_balanced_portfolio.py'
    spec=importlib.util.spec_from_file_location('corrected_multi',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def convert(frame,currency,fx):
        if currency.upper()=='CNY':return frame.copy()
        if currency.upper()!='USD':raise ValueError(currency)
        # Caller doesn't pass symbol; identify a frame by its index and OHLC object
        # via the frozen assets loaded below, without guessing calendar from values.
        for symbol,raw in raw_us.items():
            if frame is raw or frame.equals(raw): return fx_at_open(frame,symbol,fx)
        raise ValueError('Unidentified USD asset')
    assets=module.expand_assets(module.load_config(module.DEFAULT_CONFIG),module.DEFAULT_CONFIG.parent)
    raw,missing,fx=module.load_all_frames(assets,'CNY=X',snapshot)
    raw_us={a['symbol']:raw[a['symbol']] for a in assets if a.get('currency')=='USD'}
    module.normalize_ohlc_to_cny=convert
    module.simulate_monthly_portfolio=lambda frames,target_weight_fn,**kw:corrected_monthly(module,frames,target_weight_fn,**kw)
    module._asset_contributions=lambda *args,**kwargs:{'status':'NOT_RECOMPUTED_ASYNC_CLOCK', 'reason':'Legacy contribution formula assumes simultaneous fills; not used in eligibility.'}
    # Unchanged legacy RS is reference only; it cannot participate in eligibility.
    with gzip.open(ROOT/'outputs/strategy-healthcheck-2026-10-02/multi_asset_full.json.gz','rt') as stream:old=json.load(stream)
    reference=next(r for r in old['benchmarks'] if r['id']=='existing_global_rs_monthly_macd')
    reference['caveat']='UNREVIEWED LEGACY SAME-LABEL REFERENCE; reused unchanged, excluded from corrected candidate gates.'
    module._run_existing_global_rs=lambda *args,**kwargs:reference
    payload=module.build_multi_asset_balanced_research(data_dir=snapshot,end='2026-09-30')
    payload['correctedClockContract']='signal_ready_after_all_complete_bars_then_each_market_next_open_v1'
    payload['fxContract']='Known FX at each USD asset bar open, constant factor throughout bar; accounting proxy, no FX fill/settlement model.'
    payload['cashContract']='Only prior executed sales may fund purchases; instant settlement in one accounting currency; insufficient buys prorated and not automatically retried.'
    payload['researchLimitations']=['Synthetic known-FX accounting quotes, not actual FX transactions or broker settlement.',
        'Daily bars, idealized fractional fills, cash-limited one-attempt orders; not the former simultaneous execution contract.',
        'Full-period parameter gates remain research gates; no independent out-of-sample proof.']
    with gzip.open(out/'multi_asset_full.json.gz','wt') as stream:json.dump(payload,stream,ensure_ascii=False,default=module._json_default,allow_nan=False)
    text=module.render_markdown_report(payload).replace('研究 2026-06-06','时序修正研究 2026-10-03',1)
    (out/'multi_asset_full.md').write_text(text)
    prior.dump(out/'multi_asset_recommendation.json',payload['recommendation'])
    print('Multi complete:',payload['recommendation'],flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--family',choices=['btc','multi'],required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    (run_btc if args.family=='btc' else run_multi)(args.snapshot,args.output)


if __name__=='__main__':main()
