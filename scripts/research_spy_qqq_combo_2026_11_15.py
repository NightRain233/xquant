"""SPY+QQQ combination strategies: fixed mix, inverse volatility, and relative momentum."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from research_qqq_new_enhance_2026_11_14 import build_data, run as run_old, monthly_q5, drawdown_events, START, END, COST, COST30
from xquant import overlay_rules as ov
SLUG='spy-qqq-combo-2026-11-15'; OUT=ROOT/'outputs'/SLUG
SEGMENTS={'2000-2012':(START,pd.Timestamp('2012-12-31')),'2013-2026':(pd.Timestamp('2013-01-01'),END)}

def signal_state(states,start_i):
    states=np.asarray(states,float)
    return ov.state_signal(states,start_i)

def fixed_mix_signal(wq, ws, dates, start_i, monthly=True):
    me=ov.month_end_mask(dates)
    def sig(i,_w):
        if i==start_i or (monthly and me[i]): return np.array([wq,ws],float)
        return None
    return sig

def invvol_signal(qqq,spy,dates,start_i,window=21):
    qv=np.log(qqq).diff().rolling(window).std(ddof=1)*np.sqrt(252)
    sv=np.log(spy).diff().rolling(window).std(ddof=1)*np.sqrt(252)
    me=ov.month_end_mask(dates); state=np.full((len(dates),2),np.nan)
    for i in np.flatnonzero(me):
        a,b=qv.iloc[i],sv.iloc[i]
        if np.isfinite(a) and np.isfinite(b) and a>0 and b>0:
            iq, iw=1/a,1/b; state[i]=[iq/(iq+iw),iw/(iq+iw)]
    state=pd.DataFrame(state,index=dates).ffill().fillna(0.5).to_numpy()
    def sig(i,_w):
        if i==start_i or i>start_i and (me[i] and not np.allclose(state[i],state[i-1])): return state[i]
        return None
    return sig

def rel_signal(qqq,spy,cash,dates,start_i,lookback=12,sma_months=10):
    idx=np.flatnonzero(ov.month_end_mask(dates)); qm=qqq.iloc[idx]; sm=spy.iloc[idx]; cm=cash.iloc[idx]
    qr=qm/qm.shift(lookback)-1; sr=sm/sm.shift(lookback)-1; cr=cm/cm.shift(lookback)-1
    q_on=(qr>sr)&(qr>cr)&(qm>qm.rolling(sma_months).mean())
    s_on=(sr>=qr)&(sr>cr)&(sm>sm.rolling(sma_months).mean())
    states=np.zeros((len(idx),2)); states[q_on.to_numpy()]=[1.,0.]; states[(~q_on&s_on).to_numpy()]=[0.,1.]
    full=pd.DataFrame(states,index=dates[idx]).reindex(dates,method='ffill').fillna(0).to_numpy()
    return signal_state(full,start_i)

def mtf_blend(qqq,spy,dates,start_i):
    # independent MTF states; equalize only active legs, cash if neither active
    from research_513500_mtf_tvt_real_2026_11_14 import stage_states,month_state,latest_before
    qw=stage_states(qqq); sw=stage_states(spy); qm=month_state(qqq); sm=month_state(spy)
    states=[]
    for d in dates:
        qa=latest_before(qw.astype(float),d,0)>0.5 and latest_before(qm,d,0)>0.5
        sa=latest_before(sw.astype(float),d,0)>0.5 and latest_before(sm,d,0)>0.5
        if qa and sa: states.append([.5,.5])
        elif qa: states.append([1.,0.])
        elif sa: states.append([0.,1.])
        else: states.append([0.,0.])
    return signal_state(np.asarray(states),start_i)

def execute(data, qqq, spy, name, cost=COST, params=None):
    dates=data.dates; start_i=int(dates.searchsorted(START)); prices=pd.DataFrame({'a':qqq,'b':spy},index=dates); cash_idx=pd.Series(np.cumprod(data.cash_pos),index=dates)
    if name=='SPY': sig=fixed_mix_signal(0,1,dates,start_i)
    elif name=='QQQ': sig=fixed_mix_signal(1,0,dates,start_i)
    elif name=='50_50': sig=fixed_mix_signal(.5,.5,dates,start_i)
    elif name=='60Q_40S': sig=fixed_mix_signal(.6,.4,dates,start_i)
    elif name=='INVVOL': sig=invvol_signal(qqq,spy,dates,start_i, (params or {}).get('window',21))
    elif name=='REL-12': sig=rel_signal(qqq,spy,cash_idx,dates,start_i,(params or {}).get('lookback',12),(params or {}).get('sma_months',10))
    elif name=='MTF-BLEND': sig=mtf_blend(qqq,spy,dates,start_i)
    else: raise ValueError(name)
    res=ov.run_overlay(prices,sig,start_i,cost,data.cash_pos,data.cash_neg)
    m=ov.perf_metrics(res.nav,res.tbill_daily,res.weights['a'],ov.count_trades(res)); m['avg_qqq_weight']=float(res.weights.a.iloc[1:].mean()); m['avg_spy_weight']=float(res.weights.b.iloc[1:].mean()); m['avg_gross_weight']=float(res.weights.iloc[1:].sum(axis=1).mean())
    return res,m

def main():
    OUT.mkdir(parents=True,exist_ok=True); data,qqq,spy,bill=build_data(); labels=['SPY','QQQ','50_50','60Q_40S','INVVOL','REL-12','MTF-BLEND']; results={n:execute(data,qqq,spy,n) for n in labels}
    rows=[]
    for n,(r,m) in results.items(): rows.append({'strategy':n,**m,**monthly_q5(r.nav),'asset':'SPY+QQQ','window':'2000-2026','cost':'10bp'})
    pd.DataFrame(rows).to_csv(OUT/'summary_q3_q5.csv',index=False)
    pd.DataFrame({n:r.nav for n,(r,_) in results.items()}).to_csv(OUT/'nav_daily.csv',index_label='date')
    pd.DataFrame({n:r.weights.a for n,(r,_) in results.items()}).to_csv(OUT/'qqq_weights_daily.csv',index_label='date')
    pd.DataFrame({n:r.weights.b for n,(r,_) in results.items()}).to_csv(OUT/'spy_weights_daily.csv',index_label='date')
    pd.DataFrame({n:ov.yearly_returns(r.nav) for n,(r,_) in results.items()}).to_csv(OUT/'yearly_returns.csv',index_label='year')
    pd.concat([drawdown_events(r.nav).assign(strategy=n) for n,(r,_) in results.items()],ignore_index=True).to_csv(OUT/'drawdown_events.csv',index=False)
    seg=[]
    for n,(r,_) in results.items():
        for lab,(a,b) in SEGMENTS.items(): seg.append({'strategy':n,'segment':lab,**ov.perf_metrics(ov.segment_slice(r.nav,a,b),r.tbill_daily,r.weights.a,0)})
    pd.DataFrame(seg).to_csv(OUT/'segments.csv',index=False)
    c30=[]
    for n in labels:
        r,m=execute(data,qqq,spy,n,COST30); c30.append({'strategy':n,'cost':'30bp',**m})
    pd.DataFrame(c30).to_csv(OUT/'cost30.csv',index=False)
    sens=[]
    for w in (10,21,42):
        r,m=execute(data,qqq,spy,'INVVOL',params={'window':w}); sens.append({'family':'INVVOL','variant':f'window{w}',**m})
    for lb in (6,12,18):
        for sma in (8,10,12):
            r,m=execute(data,qqq,spy,'REL-12',params={'lookback':lb,'sma_months':sma}); sens.append({'family':'REL-12','variant':f'lookback{lb}_sma{sma}',**m})
    pd.DataFrame(sens).to_csv(OUT/'sensitivity.csv',index=False)
    # DCA monthly 10y windows, matching QQQ study
    contrib=ov.contribution_dates(data.dates,START,END); wins=[]
    for n,(r,_) in results.items():
        for day in contrib:
            w=ov.ten_year_window(data.dates,day)
            if w is None: continue
            c,e=w; plain=ov.dca_account(results['50_50'][0].nav,c,e); acc=ov.dca_account(r.nav,c,e)
            wins.append({'strategy':n,'start':str(day.date()),'end':str(e.date()),**acc,'ratio_gt_50_50':bool(acc['ratio']>plain['ratio']),'xirr_gt_50_50':bool(acc['xirr']>plain['xirr'])})
    wf=pd.DataFrame(wins); wf.to_csv(OUT/'dca_windows.csv',index=False)
    wf.groupby('strategy').agg(n_windows=('xirr','size'),median_xirr=('xirr','median'),median_ratio=('ratio','median'),share_ratio_gt_50_50=('ratio_gt_50_50','mean'),share_xirr_gt_50_50=('xirr_gt_50_50','mean')).reset_index().to_csv(OUT/'dca_summary.csv',index=False)
    checks={'weights_in_range':all(((r.weights>=-1e-12).all().all()&(r.weights.sum(axis=1)<=1+1e-12).all()) for r,_ in results.values()),'positive_nav':all((r.nav>0).all() for r,_ in results.values())}
    (OUT/'selfcheck.json').write_text(json.dumps(checks,indent=2))
    (OUT/'config.json').write_text(json.dumps({'slug':SLUG,'window':[str(START.date()),str(END.date())],'costs':[COST,COST30],'execution':'close signal, next close fill','candidates':labels,'baseline':'SPY, QQQ, 50/50 monthly rebalance'},indent=2))
    (OUT/'README.md').write_text('# SPY+QQQ组合研究\n\n比较固定配比、逆波动、相对动量与独立多周期趋势组合。美元分红复权价格，收盘信号下一收盘执行。\n')
if __name__=='__main__': main()
