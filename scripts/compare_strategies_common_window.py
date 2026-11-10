"""Common-window comparison of the 2026-11 S&P rules (S2, VT-1.0) against the strategies already in the repo.

Run (from repo root):
  uv run python -I scripts/compare_strategies_common_window.py

Every series is cut to the same window and normalized to 1 at its first day. Metrics use one definition for all
rows: annualized return, annual volatility, Sharpe with a zero risk-free rate, max drawdown, return/drawdown ratio
(Calmar), worst rolling 3-year annualized return and longest underwater spell. Sharpe here uses a zero risk-free rate,
so it differs slightly from the T-bill-excess numbers in the individual reviews.
Series in different currencies are shown in their own currency and not converted.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]
from xquant import style_combo as sc  # noqa: E402

OUT = ROOT / "outputs" / "strategy-comparison-2026-11-10"
WINDOW = ("2016-06-21", "2026-06-23")

# (label, currency, csv path, column, note on the source)
# A row may carry a 6th element: the strategy name inside a file that stacks several strategies.
SOURCES = [
    ("主线：三组合核心（无 BTC）", "人民币", "outputs/btc-satellite-corrected-prices-2026-10-18/nav_BTC_0.csv", "nav", "修正复权口径"),
    ("主线：三组合 + 7.5% BTC 卫星", "人民币", "outputs/btc-satellite-corrected-prices-2026-10-18/nav_BTC_7.5.csv", "nav", "修正复权口径"),
    ("红利低波 买入持有（指数）", "人民币", "outputs/dividend-lowvol-bollinger-2026-11-05/nav_daily.csv", "红利低波买入持有", "全收益指数"),
    ("沪深300 全收益 买入持有", "人民币", "outputs/dividend-lowvol-csi2000-2026-10-18/nav_daily.csv", "沪深300全收益买入持有", "全收益指数"),
    ("冻结研究线：风险平价核心（scan-v2）", "人民币", "outputs/scan-v2-all-bull-flip-defense/nav_daily.csv", "nav", "冻结研究线", "risk_parity_core"),
    ("冻结研究线：核心90% + Bull Flip 10%", "人民币", "outputs/scan-v2-all-bull-flip-defense/nav_daily.csv", "nav", "冻结研究线，纸面并行", "core90_bull10"),
    ("冻结研究线：核心90% + MA200过滤 Bull Flip 10%", "人民币", "outputs/scan-v2-all-bull-flip-defense/nav_daily.csv", "nav", "冻结研究线，纸面并行", "core90_def200_bull10"),
    ("冻结研究线：Bull Flip 原始基线", "人民币", "outputs/scan-v2-all-bull-flip-defense/nav_daily.csv", "nav", "冻结研究线", "bull_flip_baseline"),
    ("温斯坦阶段2（ETF 池，30 周）", "人民币", "outputs/weinstein-etf-stage-2026-10-18/nav_daily.csv", "温斯坦阶段2策略(30周,主结果)", "A 股 ETF 池"),
    ("标普500 持有（SPY）", "美元", "outputs/sp500-enhance-vs-dca-2026-11-10/nav_daily.csv", "B0", "分红再投资"),
    ("标普500 半仓趋势（S2）", "美元", "outputs/sp500-enhance-vs-dca-2026-11-10/nav_daily.csv", "S2", "本次新研究"),
    ("标普500 15% 目标波动率（VT-1.0）", "美元", "outputs/sp500-enhance-vs-dca-2026-11-10/nav_daily.csv", "VT-1.0", "本次新研究"),
    ("标普500 1.5 倍趋势杠杆（S1）", "美元", "outputs/sp500-enhance-vs-dca-2026-11-10/nav_daily.csv", "S1", "2026-11-05 研究"),
    ("标普500 失业率+趋势（GTT）", "美元", "outputs/sp500-enhance-vs-dca-2026-11-10/nav_daily.csv", "GTT", "本次新研究的对照规则"),
    ("513500 标普 持有（境内价格）", "人民币", "outputs/domestic-us-etf-trend-2026-11-10/nav_daily_513500.csv", "513500 持有", "真实成交价"),
    ("513500 半仓趋势（美股信号，境内价格）", "人民币", "outputs/domestic-us-etf-trend-2026-11-10/nav_daily_513500.csv", "513500 半仓趋势(美股信号)", "真实成交价"),
    ("513500 半仓趋势（境内信号，境内价格）", "人民币", "outputs/domestic-us-etf-trend-2026-11-10/nav_daily_513500.csv", "513500 半仓趋势(境内自身信号)", "真实成交价"),
    ("513100 纳指 持有（境内价格）", "人民币", "outputs/domestic-us-etf-trend-2026-11-10/nav_daily_513100.csv", "513100 持有", "真实成交价"),
    ("513100 半仓趋势（境内信号，境内价格）", "人民币", "outputs/domestic-us-etf-trend-2026-11-10/nav_daily_513100.csv", "513100 半仓趋势(境内自身信号)", "真实成交价"),
]


def load_series(path: str, column: str, strategy: str | None = None) -> pd.Series:
    df = pd.read_csv(ROOT / path, encoding="utf-8-sig")
    if strategy is not None:
        df = df[df["strategy"] == strategy]
    date_col = df.columns[0]
    dates = pd.to_datetime(df[date_col].astype(str).str[:10], format="%Y-%m-%d")
    s = pd.Series(df[column].to_numpy(float), index=dates).dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def cut(s: pd.Series) -> pd.Series:
    start, end = pd.Timestamp(WINDOW[0]), pd.Timestamp(WINDOW[1])
    first = s[s.index >= start]
    if first.empty:
        raise ValueError("series does not cover the window")
    seg = first[first.index <= end]
    return seg / seg.iloc[0]


def metrics(nav: pd.Series) -> dict:
    ret = nav.pct_change().dropna()
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = float(nav.iloc[-1] ** (1 / years) - 1)
    vol = float(ret.std(ddof=1) * np.sqrt(252))
    sharpe = float(ret.mean() / ret.std(ddof=1) * np.sqrt(252))
    dd = float(sc.drawdown(nav).min())
    worst3, _ = sc.rolling_worst(nav)
    recovery_days, _ = sc.longest_recovery_days(nav)
    return {"cagr": cagr, "vol": vol, "sharpe": sharpe, "max_dd": dd,
            "calmar": cagr / abs(dd) if dd else float("nan"), "worst_3y_annualized": worst3,
            "longest_underwater_years": round(recovery_days / 365.25, 2), "final_multiple": float(nav.iloc[-1]),
            "start": str(nav.index[0].date()), "end": str(nav.index[-1].date()), "days": len(nav)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in SOURCES:
        label, currency, path, column, source_note = entry[:5]
        strategy = entry[5] if len(entry) > 5 else None
        nav = cut(load_series(path, column, strategy))
        row = {"strategy": label, "currency": currency, "source": path.split("/", 1)[1], "column": column,
               "source_note": source_note}
        row.update(metrics(nav))
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "comparison.csv", index=False)
    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 42)
    show = table[["strategy", "currency", "cagr", "vol", "sharpe", "max_dd", "calmar", "worst_3y_annualized",
                  "longest_underwater_years", "final_multiple", "start", "end"]]
    print(show.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
