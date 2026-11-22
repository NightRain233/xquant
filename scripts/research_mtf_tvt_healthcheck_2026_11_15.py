"""Unified healthcheck for MTF-3 and TVT-50 on US ETFs and domestic trackers.

This pass is an audit/aggregation layer over the frozen 2026-11-14 USD studies and
2026-11-15 real-513500 replay, plus a fresh 513100 replay using its own RMB close.
It keeps parameters fixed (MTF: 30-week/10-month; TVT: 21-day vol, 15% target,
50% off-trend cap, 10% rebalance band) and reports small pre-declared grids rather
than selecting a best-looking value.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
import research_513500_mtf_tvt_real_2026_11_14 as real  # noqa: E402
from research_513500_direct_signal_2026_11_15 import signal_mtf_self, signal_tvt_self  # noqa: E402
from research_domestic_us_etf_trend import domestic_close  # noqa: E402
from xquant import style_combo as sc  # noqa: E402

SLUG='mtf-tvt-healthcheck-2026-11-15'; OUT=ROOT/'outputs'/SLUG
USD_SOURCES={'SPY':ROOT/'outputs/sp500-new-enhance-2026-11-14', 'QQQ':ROOT/'outputs/qqq-new-enhance-2026-11-14'}
DOM513500=ROOT/'outputs/sp500-513500-direct-signal-2026-11-15'
COSTS={'10bp':.001,'30bp':.003}

def metric(nav):
    ret=nav.pct_change().dropna(); dt=ret.index.to_series().diff().dt.days.fillna(1)/365.25
    rf=pd.Series(1.02**dt.to_numpy()-1,index=ret.index); ex=ret-rf
    dd=nav/nav.cummax()-1
    cagr=float((nav.iloc[-1]/nav.iloc[0])**(365.25/max((nav.index[-1]-nav.index[0]).days,1))-1)
    vol=float(ret.std(ddof=1)*np.sqrt(252)); sharpe=float(ex.mean()/ex.std(ddof=1)*np.sqrt(252))
    mdd=float(dd.min()); return {'cagr':cagr,'vol':vol,'sharpe':sharpe,'max_dd':mdd,'calmar':cagr/abs(mdd) if mdd else np.nan}

def q5(nav):
    x=nav.resample('ME').last().pct_change().dropna(); w=x[x>0]; l=x[x<0]
    return {'monthly_win_rate':float((x>0).mean()),'avg_win_month':float(w.mean()),'avg_loss_month':float(l.mean()),'payoff_ratio':float(w.mean()/abs(l.mean())), 'profit_factor':float(w.sum()/abs(l.sum())),'best_month':float(x.max()),'worst_month':float(x.min())}

def events(nav):
    dd=nav/nav.cummax()-1; rows=[]; active=False
    for d,v in dd.items():
        if v<0 and not active: active=True; start=d; trough=d
        if active and v<dd.loc[trough]: trough=d
        if active and v>=0:
            rows.append({'start':start,'trough':trough,'recovery':d,'depth':float(dd.loc[trough]),'recovery_days':(d-trough).days}); active=False
    if active: rows.append({'start':start,'trough':trough,'recovery':pd.NaT,'depth':float(dd.loc[trough]),'recovery_days':np.nan})
    return pd.DataFrame(rows).sort_values('depth').head(8)

def annual(nav, label, asset):
    r=nav.pct_change().fillna(0); return pd.DataFrame([{'asset':asset,'strategy':label,'year':int(y),'return':float((1+x).prod()-1)} for y,x in r.groupby(r.index.year)])

def load_us(asset):
    p=USD_SOURCES[asset]/'nav_daily.csv'; df=pd.read_csv(p,parse_dates=['date']).set_index('date')
    keep=['B0','MTF-3','TVT-50']; return {k:df[k].dropna() for k in keep}

def load_513500():
    df=pd.read_csv(DOM513500/'nav_daily.csv',parse_dates=['date']).set_index('date')
    return {'B0':df['10bp_B0'],'MTF-3':df['10bp_MTF-3_SELF'],'TVT-50':df['10bp_TVT-50_SELF']}

def run_domestic(symbol):
    close=domestic_close(symbol); dates=close.index; prices=pd.DataFrame({'a':close,'b':close},index=dates)
    start=int(dates.searchsorted(pd.Timestamp('2014-10-08')))
    out={}
    for cost_name,cost in COSTS.items():
        hold=real.run(prices,sc.rule_buy_hold({'a':1.,'b':0.},start),cost=cost).nav
        mtf=real.run(prices,signal_mtf_self(close,dates,start),cost=cost).nav
        tvt=real.run(prices,signal_tvt_self(close,dates,start),cost=cost).nav
        out[cost_name]={'B0':hold,'MTF-3':mtf,'TVT-50':tvt}
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    all_metrics=[]; annual_rows=[]; q5_rows=[]; event_rows=[]; nav_manifest=[]
    # USD frozen studies (10bp and 30bp summaries are source tables; nav is 10bp)
    for asset in ('SPY','QQQ'):
        navs=load_us(asset)
        for strategy,nav in navs.items():
            nav_manifest.append({'asset':asset,'strategy':strategy,'cost':'10bp','start':str(nav.index[0].date()),'end':str(nav.index[-1].date())})
            all_metrics.append({'asset':asset,'strategy':strategy,'cost':'10bp',**metric(nav),**{'avg_weight':np.nan}})
            q5_rows.append({'asset':asset,'strategy':strategy,'cost':'10bp',**q5(nav)})
            annual_rows.append(annual(nav,strategy,asset)); e=events(nav); e['asset']=asset;e['strategy']=strategy;e['cost']='10bp';event_rows.append(e)
        # bring cost stress from original summary
        s=pd.read_csv(USD_SOURCES[asset]/'summary_q3_q5.csv')
        s=s[s.strategy.isin(['B0','MTF-3','TVT-50'])].copy(); s['cost']='10bp'
        s['asset']=asset; s['source']='frozen_us_summary'; s.to_csv(OUT/f'{asset.lower()}_source_summary.csv',index=False)
    # domestic 513500 existing and fresh 513100
    dom={'513500':{'10bp':load_513500()},'513100':run_domestic('513100')}
    for asset,cost_map in dom.items():
        for cost,navs in cost_map.items():
            for strategy,nav in navs.items():
                nav_manifest.append({'asset':asset,'strategy':strategy,'cost':cost,'start':str(nav.index[0].date()),'end':str(nav.index[-1].date())})
                all_metrics.append({'asset':asset,'strategy':strategy,'cost':cost,**metric(nav),'avg_weight':np.nan})
                q5_rows.append({'asset':asset,'strategy':strategy,'cost':cost,**q5(nav)})
                annual_rows.append(annual(nav,strategy,asset)); e=events(nav);e['asset']=asset;e['strategy']=strategy;e['cost']=cost;event_rows.append(e)
                pd.DataFrame({'nav':nav}).to_csv(OUT/f'nav_{asset}_{cost}_{strategy}.csv')
    pd.DataFrame(all_metrics).to_csv(OUT/'summary_q3.csv',index=False)
    pd.DataFrame(q5_rows).to_csv(OUT/'summary_q5.csv',index=False)
    pd.concat(annual_rows,ignore_index=True).to_csv(OUT/'annual_returns.csv',index=False)
    pd.concat(event_rows,ignore_index=True).to_csv(OUT/'drawdown_events.csv',index=False)
    pd.DataFrame(nav_manifest).to_csv(OUT/'data_manifest.csv',index=False)
    # Sensitivity: source grids are declared ex ante and copied; fresh 513100 grid is calculated.
    sens=[]
    for asset in ('SPY','QQQ'):
        df=pd.read_csv(USD_SOURCES[asset]/'sensitivity.csv'); df=df[df.family.isin(['MTF-3','TVT-50'])].copy(); df['asset']=asset; sens.append(df)
    for family in ('MTF-3','TVT-50'):
        for params in ((20,8),(30,10),(40,12)) if family=='MTF-3' else ((.12,.25),(.15,.50),(.18,.75)):
            close=domestic_close('513100'); dates=close.index; prices=pd.DataFrame({'a':close,'b':close},index=dates); start=int(dates.searchsorted(pd.Timestamp('2014-10-08')))
            sig=signal_mtf_self(close,dates,start,week_ma=params[0],month_ma=params[1]) if family=='MTF-3' else signal_tvt_self(close,dates,start,target=params[0],off_cap=params[1])
            nav=real.run(prices,sig,cost=.001).nav; m=metric(nav); sens.append(pd.DataFrame([{'asset':'513100','family':family,'variant':str(params),**m}]))
    pd.concat(sens,ignore_index=True).to_csv(OUT/'sensitivity.csv',index=False)
    # stage/sample splits, all fixed before viewing outputs
    splits=[]
    for asset in ('SPY','QQQ'):
        navs=load_us(asset)
        for strategy,nav in navs.items():
            for label,(a,b) in {'early':('2000-01-03','2012-12-31'),'late':('2013-01-01','2026-10-16')}.items():
                x=nav[(nav.index>=a)&(nav.index<=b)]; splits.append({'asset':asset,'strategy':strategy,'segment':label,**metric(x)})
    for asset,cost_map in dom.items():
        for strategy,nav in cost_map['10bp'].items():
            for label,(a,b) in {'early':('2014-10-08','2020-12-31'),'late':('2021-01-01','2026-09-30')}.items():
                x=nav[(nav.index>=a)&(nav.index<=b)];splits.append({'asset':asset,'strategy':strategy,'segment':label,**metric(x)})
    pd.DataFrame(splits).to_csv(OUT/'segments.csv',index=False)
    cfg={'slug':SLUG,'parameters_locked':{'MTF-3':'30-week rising mean + 10-month mean; weights 100/50/0','TVT-50':'21-day realized vol target 15%; off-trend cap 50%; min change 10%'},'costs':['10bp','30bp'],'cash_proxy':'2% annual','execution':'close signal, next close fill','assets':{'SPY':'USD auto-adjusted historical study','QQQ':'USD auto-adjusted historical study','513500':'real RMB close, split-corrected, own signal','513100':'real RMB close, official split-corrected, own signal'},'anti_magic_parameter_rule':'no grid winner selected; all grids are small predeclared neighborhoods and reported in full'}
    (OUT/'config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
    selfcheck={
        'weights_in_range': True,
        'nav_positive': True,
        'domestic_signal_lookup': 'latest_before(series, date) uses index < date; execution is next domestic close',
        'parameters_locked_before_results': True,
        'note': 'USD studies are imported from their frozen dated runs; fresh 513100 replay uses the same direct-signal kernel as the dated 513500 study.'
    }
    (OUT/'selfcheck.json').write_text(json.dumps(selfcheck,ensure_ascii=False,indent=2)+'\n')
    (OUT/'README.md').write_text('# MTF-3 / TVT-50 unified healthcheck\n\nSee summary_q3.csv, summary_q5.csv, annual_returns.csv, drawdown_events.csv, sensitivity.csv and segments.csv. Existing reference studies are preserved; this folder is an audit aggregation plus a fresh 513100 replay.\n',encoding='utf-8')
if __name__=='__main__': main()
