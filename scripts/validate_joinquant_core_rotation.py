"""Validation suite for the JoinQuant four-ETF rotation study."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("outputs/joinquant-core-rotation-2026-11-15")
OUT = ROOT / "validation"
OUT.mkdir(parents=True, exist_ok=True)


def score_matrix(close, short, long=200, reversal_weight=6):
    p = np.log(close.to_numpy(float)); n, k = p.shape
    out = np.full((n, k), np.nan)
    def reg(y):
        m = y.shape[0]; t = np.arange(m, dtype=float); tc = t - t.mean(); den = np.sum(tc * tc)
        slopes = np.sum((y - y.mean(axis=0)) * tc[:, None], axis=0) / den
        fit = y.mean(axis=0) + slopes[None, :] * tc[:, None]
        sse = np.sum((y - fit) ** 2, axis=0); sst = np.sum((y - y.mean(axis=0)) ** 2, axis=0)
        r2 = np.where(sst > 0, 1 - sse / sst, 0)
        return (np.exp(slopes) ** 250 - 1) * r2
    for i in range(long - 1, n):
        out[i] = reg(p[i - short + 1:i + 1]) - reg(p[i - long + 1:i + 1]) / reversal_weight
    return pd.DataFrame(out, index=close.index, columns=close.columns)


def nav_top1(close, scores):
    chosen = scores.fillna(-np.inf).idxmax(axis=1).where(scores.notna().any(axis=1))
    held = chosen.shift(1); ret = close.pct_change().fillna(0)
    gross = pd.Series(0.0, index=close.index); turn = pd.Series(0.0, index=close.index); prev = None
    for d, a in held.items():
        if pd.notna(a): gross.loc[d] = ret.loc[d, a]
        if a != prev: turn.loc[d] = 1 if prev is None or pd.isna(prev) else 2
        prev = a
    return 100 * (1 + gross - turn * 24 / 10000).cumprod(), chosen


def nav_iv(close, window=20):
    r = close.pct_change(); vol = r.rolling(window).std() * np.sqrt(252)
    w = (1 / vol).div((1 / vol).sum(axis=1), axis=0).replace([np.inf, -np.inf], np.nan).fillna(0)
    held = w.shift(1).fillna(0); ret = close.pct_change().fillna(0)
    gross = (held * ret).sum(axis=1); turn = held.diff().abs().sum(axis=1).fillna(1) / 2
    return 100 * (1 + gross - turn * 24 / 10000).cumprod()


def metrics(nav, start=None, end=None):
    x = nav.loc[start:end].dropna() if start or end else nav.dropna(); r = x.pct_change().dropna()
    years = (x.index[-1] - x.index[0]).days / 365.25; dd = x / x.cummax() - 1
    return {"start": str(x.index[0].date()), "end": str(x.index[-1].date()), "total": x.iloc[-1] / x.iloc[0] - 1,
            "cagr": (x.iloc[-1] / x.iloc[0]) ** (1 / years) - 1, "vol": r.std() * np.sqrt(252),
            "max_dd": dd.min(), "sharpe": r.mean() / r.std() * np.sqrt(252)}


if __name__ == "__main__":
    close = pd.read_csv(ROOT / "prices_adj_close.csv", index_col=0, parse_dates=True).dropna()
    # Fine grid: enough to reveal a narrow optimum without optimizing noise.
    grid = []
    for short in (15, 20, 25, 30, 35, 40, 50, 60):
        for weight in (3, 6, 999999):
            nav, _ = nav_top1(close, score_matrix(close, short, reversal_weight=weight))
            row = metrics(nav); row.update(short=short, reversal_weight=weight); grid.append(row)
    pd.DataFrame(grid).to_csv(OUT / "parameter_grid.csv", index=False)
    # Walk-forward-style fixed subperiod checks using the same unoptimized parameters.
    scores = score_matrix(close, 25, reversal_weight=6); nav, _ = nav_top1(close, scores)
    folds = [("2014_2018", "2014-12-31", "2018-12-31"), ("2019_2022", "2019-01-01", "2022-12-31"), ("2023_2026", "2023-01-01", "2026-09-30")]
    rows = []
    for name, start, end in folds:
        row = metrics(nav, start, end); row["fold"] = name; rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "walk_forward_folds.csv", index=False)
    # Leave-one-asset-out ablation.
    rows = []
    for removed in [None, *close.columns]:
        c = close.drop(columns=[removed]) if removed else close
        n, _ = nav_top1(c, score_matrix(c, 25, reversal_weight=6)); row = metrics(n); row["removed"] = removed or "none"; rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "leave_one_out.csv", index=False)
    # Four-asset inverse-volatility comparison.
    iv = nav_iv(close, 20); row = metrics(iv); row["strategy"] = "four_asset_IV20"; pd.DataFrame([row]).to_csv(OUT / "four_asset_inverse_volatility.csv", index=False)
    print(pd.DataFrame(grid).sort_values("sharpe", ascending=False).head(10).to_string(index=False))
