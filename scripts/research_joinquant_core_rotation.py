"""Reproduce the JoinQuant four-ETF core-asset rotation article.

The article's published rule is daily single-asset selection by a 25-day
log-price regression score, with a 200-day reversal term.  The RSRS filter
is reported separately because the page does not publish countBeta().
"""
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path("outputs/joinquant-core-rotation-2026-11-15")
OUT.mkdir(parents=True, exist_ok=True)
TICKERS = {"518880.SS": "黄金ETF", "513100.SS": "纳指ETF", "159915.SZ": "创业板ETF", "510180.SS": "上证180ETF"}


def download_prices():
    raw = yf.download(list(TICKERS), start="2014-01-01", end="2026-11-16", auto_adjust=False, progress=False, group_by="column", threads=False)
    close = raw["Adj Close"] if "Adj Close" in raw else raw["Close"]
    close = close.rename(columns=TICKERS).dropna(how="all").ffill()
    close.to_csv(OUT / "prices_adj_close.csv")
    return close


def score(series, short=25, long=200):
    if len(series) < long:
        return np.nan
    def one(x):
        y = np.log(x.to_numpy(float)); t = np.arange(len(y))
        slope, intercept = np.polyfit(t, y, 1)
        fit = slope * t + intercept
        denom = (len(y) - 1) * np.var(y, ddof=1)
        r2 = 1 - np.sum((y - fit) ** 2) / denom if denom else 0.0
        return (np.exp(slope) ** 250 - 1) * r2
    return one(series.iloc[-short:]) - one(series.iloc[-long:]) / 6.0


def backtest(close, short=25, reversal_weight=6, cost_bps=24):
    # cost_bps approximates the article's 0.2% fixed slippage + 0.02% commission.
    dates = close.index
    scores = pd.DataFrame(index=dates, columns=close.columns, dtype=float)
    for i in range(len(close)):
        if i + 1 >= 200:
            for c in close.columns:
                    scores.iloc[i, scores.columns.get_loc(c)] = score(close[c].iloc[: i + 1], short, 200) if reversal_weight == 6 else score_variant(close[c].iloc[: i + 1], short, 200, reversal_weight)
    valid = scores.notna().any(axis=1)
    # Signal is known after the close; hold the selected ETF on the next day.
    chosen = scores.fillna(-np.inf).idxmax(axis=1).where(valid)
    held = chosen.shift(1)
    ret = close.pct_change().fillna(0.0)
    gross = pd.Series(0.0, index=dates)
    turnover = pd.Series(0.0, index=dates)
    prev = None
    for d in dates:
        asset = held.loc[d]
        if asset is not None and pd.notna(asset):
            gross.loc[d] = ret.loc[d, asset]
        if asset != prev:
            turnover.loc[d] = 1.0 if prev is None or pd.isna(prev) else 2.0
        prev = asset
    net = gross - turnover * cost_bps / 10000
    nav = 100 * (1 + net).cumprod()
    out = pd.DataFrame({"nav": nav, "daily_return": net, "chosen": chosen, "held": held, **{f"score_{c}": scores[c] for c in close.columns}})
    out.to_csv(OUT / "nav_daily.csv")
    return out


def score_variant(series, short, long, reversal_weight):
    def one(x):
        y = np.log(x.to_numpy(float)); t = np.arange(len(y)); slope, intercept = np.polyfit(t, y, 1)
        fit = slope * t + intercept; denom = (len(y) - 1) * np.var(y, ddof=1)
        r2 = 1 - np.sum((y - fit) ** 2) / denom if denom else 0.0
        return (np.exp(slope) ** 250 - 1) * r2
    return one(series.iloc[-short:]) - one(series.iloc[-long:]) / reversal_weight


def metrics(nav):
    r = nav.pct_change().dropna(); years = (nav.index[-1] - nav.index[0]).days / 365.25
    dd = nav / nav.cummax() - 1
    monthly = nav.resample("ME").last().pct_change().dropna()
    return {"start": str(nav.index[0].date()), "end": str(nav.index[-1].date()), "total_return": nav.iloc[-1] / nav.iloc[0] - 1,
            "cagr": (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1, "volatility": r.std() * np.sqrt(252),
            "max_drawdown": dd.min(), "sharpe": r.mean() / r.std() * np.sqrt(252),
            "monthly_win_rate": (monthly > 0).mean(), "avg_win_month": monthly[monthly > 0].mean(),
            "avg_loss_month": monthly[monthly < 0].mean(), "turnover_days": int((out["chosen"] != out["chosen"].shift()).sum())}


if __name__ == "__main__":
    close = download_prices()
    out = backtest(close)
    m = metrics(out["nav"])
    pd.DataFrame([m]).to_csv(OUT / "summary.csv", index=False)
    out["chosen"].value_counts(dropna=False).rename_axis("asset").to_frame("days").to_csv(OUT / "holding_days.csv")
    sens = []
    for short in (15, 25, 35):
        for weight in (3, 6, 999999):
            x = backtest(close, short=short, reversal_weight=weight)
            mm = metrics(x["nav"]); mm.update(short=short, reversal_weight=weight)
            sens.append(mm)
    pd.DataFrame(sens).to_csv(OUT / "sensitivity.csv", index=False)
    print(pd.DataFrame([m]).T.to_string(header=False))
