"""Three focused IV20 extensions: gold trend gate, momentum gate, and defensive replacements."""
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_joinquant_core_rotation import metrics

ROOT = Path("outputs/joinquant-core-rotation-2026-11-15")
OUT = ROOT / "validation"


def iv_weights(close, window=20):
    vol = close.pct_change().rolling(window).std() * np.sqrt(252)
    inv = 1 / vol
    return inv.div(inv.sum(axis=1), axis=0).replace([np.inf, -np.inf], np.nan).fillna(0)


def replay(close, weights):
    w = weights.shift(1).fillna(0); r = close.pct_change().fillna(0)
    cash = (1 - w.sum(axis=1)).clip(lower=0)
    gross = (w * r).sum(axis=1)
    prev = w.shift(1).fillna(0); prev_cash = cash.shift(1).fillna(1)
    turnover = (w.sub(prev).abs().sum(axis=1) + (cash - prev_cash).abs()) / 2
    return 100 * (1 + gross - turnover * 24 / 10000).cumprod()


def summary(name, nav):
    rows=[]
    for window,start,end in [('full','2014-12-31','2026-09-30'),('recent3y','2023-10-09','2026-09-30'),('gold_bear','2014-01-02','2015-12-31'),('2022','2022-01-04','2022-12-30')]:
        m=metrics(nav,start,end); m.update(strategy=name,window=window); rows.append(m)
    return rows


if __name__ == '__main__':
    base=pd.read_csv(ROOT/'prices_adj_close.csv',index_col=0,parse_dates=True)
    raw=yf.download(['510300.SS','510880.SS','511010.SS'],start='2014-01-01',end='2026-10-01',auto_adjust=False,progress=False,group_by='column',threads=False)
    extra=(raw['Adj Close'] if 'Adj Close' in raw else raw['Close']).rename(columns={'510300.SS':'沪深300ETF','510880.SS':'红利ETF','511010.SS':'国债ETF'})
    c=pd.concat([base,extra],axis=1).ffill().dropna()
    core=['沪深300ETF','纳指ETF','黄金ETF']; gold='黄金ETF'
    rows=[]
    # 1) Gold trend gate: when gold is below its 120d MA, its weight goes to cash.
    w=iv_weights(c[core]); gate=(c[gold] > c[gold].rolling(120).mean()).astype(float).shift(1).fillna(0)
    wg=w.copy(); wg[gold]=wg[gold]*gate
    rows += summary('IV20_gold_MA120_gate', replay(c[core],wg))
    # 2) 120d momentum gate: only positive-trend assets participate; fallback to all assets.
    mom=c[core].pct_change(120); raw_w=iv_weights(c[core]); eligible=(mom>0).astype(float); wm=raw_w*eligible
    wm=wm.div(wm.sum(axis=1),axis=0).fillna(raw_w); rows += summary('IV20_momentum120_gate', replay(c[core],wm))
    # 3) defensive replacements for gold, all using pure IV20.
    for label,repl in [('dividend','红利ETF'),('bond','国债ETF')]:
        cols=['沪深300ETF','纳指ETF',repl]; x=c[cols].dropna(); rows += summary('IV20_'+label+'_replacement', replay(x,iv_weights(x)))
    out=pd.DataFrame(rows); out.to_csv(OUT/'iv20_gold_defense_experiments.csv',index=False)
    print(out[['strategy','window','cagr','max_dd','sharpe']].to_string(index=False))
