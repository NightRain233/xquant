"""Two TQQQ regime-switch rules from user posts, re-tested as written.

Run (from repo root): .venv/bin/python scripts/research_tqqq_regime_switch.py
Reads ``outputs/tqqq-regime-switch-2026-11-10/cache`` (QQQ, TQQQ) and the SPY / ^IRX caches of
``weinstein-us-sector-2026-10-18``. TQQQ before 2010-02-11 is synthetic (3x QQQ daily, calibrated below).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from research_index_enhance_strategies import load_sp500  # noqa: E402
from xquant import leveraged_switch as ls  # noqa: E402
from xquant import style_combo as sc  # noqa: E402
from xquant.weinstein_stage import load_yfinance_csv  # noqa: E402

SLUG = "tqqq-regime-switch-2026-11-10"
OUT = ROOT / "outputs" / SLUG
END = "2026-10-16"
TQQQ_INCEPTION = "2010-02-11"
FEE, SPREAD = 0.0095, 0.005
WINDOWS = {"2003": "2003-01-02", "2011": "2011-01-03", "2000": "2000-01-03"}
CONFIG = {
    "data": "yfinance auto-adjusted closes (dividends reinvested); SPY signal also uses the adjusted close",
    "tqqq": f"real TQQQ from {TQQQ_INCEPTION}; before that 3x QQQ daily minus {FEE:.2%} fee and 2x(T-bill+{SPREAD:.1%})",
    "cash": "13-week T-bill (^IRX), previous close", "execution": "signal at close, trade next close, 10bp per side",
    "end": END, "windows": WINDOWS,
    "forum": {"bull": "SPY >= 200d mean +4% -> 100% TQQQ", "bear": "SPY <= 200d mean -3% -> sell to cash",
              "between": "keep the previous state", "bear_dca": "cash into QQQ in 6 monthly tranches (21 trading days)",
              "protection": "QQQ >= own 200d mean +30% -> 50% TQQQ / 50% QQQ; >= +40% -> cash (assumption: back "
                            "to full TQQQ once below +30%)", "start": "regime from history before the window"},
    "simple": "QQQ close above its 200d mean -> 100% TQQQ, else cash (checked daily)",
    "assumptions_not_in_post": ["what 'reduce leverage' means (50/50 TQQQ/QQQ)", "6 monthly tranches",
                                "re-entry after the protection exit", "adjusted vs. raw SPY for the signal"],
}
PERIODS = {"2007-10~2009-03": ("2007-10-31", "2009-03-09"), "2011-07~10": ("2011-07-22", "2011-10-03"),
           "2015-08~2016-02": ("2015-07-20", "2016-02-11"), "2018-10~12": ("2018-10-01", "2018-12-24"),
           "2020-02~03": ("2020-02-19", "2020-03-23"), "2022全年": ("2022-01-01", "2022-12-31"),
           "2025-02~04": ("2025-02-19", "2025-04-08"), "2023至今": ("2023-01-01", END)}


def load_data():
    cache = OUT / "cache"
    spy, bill = load_sp500()
    qqq = load_yfinance_csv(cache / "yf_QQQ.csv")["close"]
    tqqq = load_yfinance_csv(cache / "yf_TQQQ.csv")["close"]
    dates = qqq.index[qqq.index <= END]
    assert spy.reindex(dates).notna().all() and tqqq.index.isin(dates).all()
    bill = bill.reindex(dates.union(bill.index)).ffill().reindex(dates)
    return spy.reindex(dates), qqq.reindex(dates), tqqq.reindex(dates), bill


def splice_tqqq(qqq, tqqq, bill, spread=SPREAD):
    synth = ls.synthetic_leveraged(qqq, bill, 3.0, FEE, spread)
    real = tqqq.dropna()
    t0 = real.index[0]
    spliced = pd.concat([synth[synth.index < t0], real / real.iloc[0] * synth.loc[t0]])
    return synth, spliced


def tracking_rows(synth, tqqq):
    real = tqqq.dropna()
    s = synth.reindex(real.index)
    yr = lambda x: x.groupby(x.index.year).last() / x.groupby(x.index.year).last().shift(1) - 1  # noqa: E731
    out = pd.DataFrame({"synthetic": yr(s), "real": yr(real)}).dropna()
    out["gap"] = out["synthetic"] - out["real"]
    out.loc["全程倍数"] = [s.iloc[-1] / s.iloc[0], real.iloc[-1] / real.iloc[0], np.nan]
    out.loc["日收益相关"] = [s.pct_change().corr(real.pct_change()), np.nan, np.nan]
    return out


class Lab:
    def __init__(self, spy, qqq, tqqq_px, bill):
        self.spy, self.qqq, self.tqqq, self.bill, self.dates = spy, qqq, tqqq_px, bill, qqq.index

    def prices(self, lev=None):
        return pd.DataFrame({"lev": self.tqqq if lev is None else lev, "base": self.qqq})

    def start(self, day):
        return int(self.dates.searchsorted(pd.Timestamp(day)))

    def run(self, decide, start, cost=0.001, lag=1, lev=None):
        i = self.start(start)
        init = decide(i, np.zeros(2))
        return ls.run_switch(self.prices(lev), self.bill, decide, i, np.zeros(2) if init is None else init, cost, lag)

    def forum(self, ma=200, up=0.04, down=0.03, dca=6, protect=True, reduced=(0.5, 0.5)):
        regime = ls.buffered_regime(ls.extension(self.spy, ma), up, down)
        return ls.forum_rule(regime, ls.extension(self.qqq, 200) if protect else None, dca, reduced=reduced)

    def simple(self, signal=None, ma=200, up=0.0, down=0.0):
        return ls.simple_rule(ls.extension(self.qqq if signal is None else signal, ma), up, down)

    def hold(self, which):
        return lambda i, w: np.array([1.0, 0.0] if which == "lev" else [0.0, 1.0])


def metrics(res, label, window):
    nav = res.nav
    m = sc.summary_metrics(nav)
    dd = sc.drawdown(nav)
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    yearly = nav.groupby(nav.index.year).last() / nav.groupby(nav.index.year).last().shift(1).fillna(nav.iloc[0]) - 1
    trough = dd.idxmin()
    return {"window": window, "strategy": label, "start": nav.index[0].date(), "annualized": m["annualized"],
            "multiple": nav.iloc[-1] / nav.iloc[0], "max_drawdown": m["max_drawdown"],
            "mdd_peak": nav[:trough].idxmax().date(), "mdd_trough": trough.date(), "annual_vol": m["annual_vol"],
            "longest_recovery_days": m["longest_recovery_days"], "time_below_minus30": float((dd < -0.3).mean()),
            "worst_year": float(yearly.min()), "worst_year_label": int(yearly.idxmin()),
            "avg_tqqq": float(res.weights["lev"].mean()), "avg_qqq": float(res.weights["base"].mean()),
            "trades_per_year": max(len(res.trades) - 1, 0) / years}


def strategies(lab):
    return {"论坛版": lab.forum(), "简化版(QQQ>200日线)": lab.simple(), "持有QQQ": lab.hold("base"),
            "持有TQQQ": lab.hold("lev")}


def period_table(results):
    rows = []
    for name, res in results.items():
        row = {"strategy": name}
        for label, (s, e) in PERIODS.items():
            seg = sc.period_stats(res.nav, s, e)
            row[label] = seg["return"] if isinstance(seg, dict) else seg
        rows.append(row)
    return pd.DataFrame(rows)


def sensitivity(lab):
    rows = []

    def add(group, label, decide, window, **kw):
        res = lab.run(decide, WINDOWS[window], **kw)
        rows.append({"group": group, "variant": label, **metrics(res, label, window)})

    for w in ("2003", "2011"):
        add(f"论坛版 {w}", "原文（4%/3%，6个月定投，保护规则）", lab.forum(), w)
        add(f"论坛版 {w}", "定投12个月", lab.forum(dca=12), w)
        add(f"论坛版 {w}", "去掉保护规则", lab.forum(protect=False), w)
        add(f"论坛版 {w}", "保护=减半到现金", lab.forum(reduced=(0.5, 0.0)), w)
        add(f"论坛版 {w}", "熊市只拿现金（不定投）", lab.forum(dca=10**6), w)
        add(f"论坛版 {w}", "缓冲 0%/0%", lab.forum(up=0.0, down=0.0), w)
        add(f"论坛版 {w}", "缓冲 2%/2%", lab.forum(up=0.02, down=0.02), w)
        add(f"论坛版 {w}", "缓冲 6%/5%", lab.forum(up=0.06, down=0.05), w)
        add(f"论坛版 {w}", "150日均线", lab.forum(ma=150), w)
        add(f"论坛版 {w}", "250日均线", lab.forum(ma=250), w)
        add(f"论坛版 {w}", "当日收盘成交", lab.forum(), w, lag=0)
        add(f"论坛版 {w}", "单边成本30bp", lab.forum(), w, cost=0.003)
        add(f"简化版 {w}", "原文（QQQ>200日线，每日）", lab.simple(), w)
        add(f"简化版 {w}", "当日收盘成交", lab.simple(), w, lag=0)
        add(f"简化版 {w}", "单边成本30bp", lab.simple(), w, cost=0.003)
        add(f"简化版 {w}", "缓冲 2%/2%", lab.simple(up=0.02, down=0.02), w)
        add(f"简化版 {w}", "缓冲 4%/3%", lab.simple(up=0.04, down=0.03), w)
        add(f"简化版 {w}", "改用SPY信号", lab.simple(signal=lab.spy), w)
        add(f"简化版 {w}", "150日均线", lab.simple(ma=150), w)
        add(f"简化版 {w}", "250日均线", lab.simple(ma=250), w)
        add(f"简化版 {w}", "同一信号拿1倍QQQ", lab.simple(), w, lev=lab.qqq)
    return pd.DataFrame(rows)


def rolling_starts(lab):
    rows = []
    strats = strategies(lab)
    for year in range(2003, 2024):
        start = f"{year}-01-01"
        row = {"start_year": year}
        for name, decide in strats.items():
            m = metrics(lab.run(decide, start), name, str(year))
            row[f"{name}_年化"], row[f"{name}_回撤"] = m["annualized"], m["max_drawdown"]
        rows.append(row)
    return pd.DataFrame(rows)


def fixed_windows(lab, years=5):
    """Every month start from 2000, the next ``years`` years: annualized return and max drawdown inside."""
    navs = {name: lab.run(decide, WINDOWS["2000"]).nav for name, decide in strategies(lab).items()}
    starts = pd.date_range("2000-01-01", pd.Timestamp(END) - pd.DateOffset(years=years), freq="MS")
    rows = []
    for s in starts:
        e = s + pd.DateOffset(years=years)
        row = {"start": s.date()}
        for name, nav in navs.items():
            seg = nav[(nav.index >= s) & (nav.index <= e)]
            row[f"{name}_年化"] = (seg.iloc[-1] / seg.iloc[0]) ** (1 / years) - 1
            row[f"{name}_回撤"] = float(sc.drawdown(seg).min())
        rows.append(row)
    return pd.DataFrame(rows)


def protection_log(lab):
    ext = ls.extension(lab.qqq, 200)
    regime = ls.buffered_regime(ls.extension(lab.spy, 200), 0.04, 0.03)
    band = pd.cut(ext, [-np.inf, 0.30, 0.40, np.inf], labels=["<30%", "30-40%", ">=40%"])
    df = pd.DataFrame({"ext": ext, "band": band, "regime": regime})
    df = df[df.index >= WINDOWS["2000"]]
    hits = df[(df["band"] != "<30%") & (df["regime"] == 1)]
    return hits.groupby([hits.index.year, "band"], observed=True).size().unstack(fill_value=0)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spy, qqq, tqqq, bill = load_data()
    synth, spliced = splice_tqqq(qqq, tqqq, bill)
    tracking = tracking_rows(synth, tqqq)
    tracking.to_csv(OUT / "synthetic_tracking.csv")
    lab = Lab(spy, qqq, spliced, bill)

    summary, results_2003, results_2011 = [], {}, {}
    for window, start in WINDOWS.items():
        for name, decide in strategies(lab).items():
            res = lab.run(decide, start)
            summary.append(metrics(res, name, window))
            if window == "2003":
                results_2003[name] = res
            if window == "2011":
                results_2011[name] = res
        summary.append(metrics(lab.run(lab.simple(), start, lev=qqq), "同一信号拿1倍QQQ", window))
    # synthetic-only check for the 2003 window (no splice to real TQQQ)
    lab_synth = Lab(spy, qqq, synth, bill)
    summary.append(metrics(lab_synth.run(lab_synth.forum(), WINDOWS["2003"]), "论坛版（全程合成TQQQ）", "2003"))
    summary = pd.DataFrame(summary)
    summary.to_csv(OUT / "summary.csv", index=False)

    period_table(results_2003).to_csv(OUT / "key_periods.csv", index=False)
    yearly = pd.DataFrame({n: r.nav.groupby(r.nav.index.year).last() for n, r in results_2003.items()})
    yearly = yearly / yearly.shift(1).fillna(pd.Series({n: r.nav.iloc[0] for n, r in results_2003.items()})) - 1
    yearly.to_csv(OUT / "yearly_returns.csv")
    pd.DataFrame({n: r.nav for n, r in results_2003.items()}).to_csv(OUT / "nav_daily_2003.csv")
    pd.DataFrame({n: r.nav for n, r in results_2011.items()}).to_csv(OUT / "nav_daily_2011.csv")
    results_2003["论坛版"].trades.to_csv(OUT / "forum_trades_2003.csv", index=False)
    results_2011["简化版(QQQ>200日线)"].trades.to_csv(OUT / "simple_trades_2011.csv", index=False)
    sensitivity(lab).to_csv(OUT / "sensitivity.csv", index=False)
    rolling_starts(lab).to_csv(OUT / "rolling_starts.csv", index=False)
    for years in (5, 10):
        fixed_windows(lab, years).to_csv(OUT / f"rolling_{years}y.csv", index=False)
    protection_log(lab).to_csv(OUT / "protection_days.csv")
    (OUT / "config.json").write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2))

    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(tracking.round(3).to_string())
    print(summary.round(3).to_string())


if __name__ == "__main__":
    main()
