"""Holding-experience measures for the S&P 500 rules of 2026-11-10 (drawdown depth, recovery, loss odds, DCA view).

Run (from repo root, after ``scripts/research_sp500_enhance_vs_dca.py``):
  uv run python -I scripts/measure_sp500_holding_experience.py

Reads the daily NAVs and the DCA summary of ``outputs/sp500-enhance-vs-dca-2026-11-10`` and writes
``outputs/holding-experience-2026-11-10``. No rule parameter is set here.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "sp500-enhance-vs-dca-2026-11-10"
OUT = ROOT / "outputs" / "holding-experience-2026-11-10"
STRATEGIES = ["B0", "S2", "VT-1.0"]
TRADING_DAYS = 252


def episodes(nav: pd.Series) -> pd.DataFrame:
    """Every spell below a previous high: peak, trough, recovery and the calendar lengths of each stage."""
    dd = (nav / nav.cummax() - 1.0).to_numpy()
    idx = nav.index
    under = dd < 0
    rows, start = [], None
    for k in range(len(nav)):
        if under[k] and start is None:
            start = k
        elif not under[k] and start is not None:
            j = start + int(np.argmin(dd[start:k]))
            rows.append((idx[start - 1], idx[j], idx[k], float(dd[j])))
            start = None
    if start is not None:
        j = start + int(np.argmin(dd[start:]))
        rows.append((idx[start - 1], idx[j], None, float(dd[j])))
    ep = pd.DataFrame(rows, columns=["peak", "trough", "recovered", "depth"])
    end = idx[-1]
    ep["peak_to_trough_days"] = (ep["trough"] - ep["peak"]).dt.days
    ep["trough_to_recovery_days"] = [(r - t).days if r is not None else np.nan
                                     for t, r in zip(ep["trough"], ep["recovered"])]
    ep["underwater_days"] = [((r if r is not None else end) - p).days
                             for p, r in zip(ep["peak"], ep["recovered"])]
    ep["still_underwater_at_end"] = ep["recovered"].isna()
    return ep


def window_loss_share(nav: pd.Series, years: int) -> tuple[float, float]:
    """Share of all start days whose holding period of ``years`` ends below the start, and its worst annualized."""
    fwd = nav.shift(-TRADING_DAYS * years) / nav - 1.0
    fwd = fwd.dropna()
    ann = (1.0 + fwd) ** (1.0 / years) - 1.0
    return float((fwd < 0).mean()), float(ann.min())


def experience_row(name: str, nav: pd.Series, ep: pd.DataFrame) -> dict:
    dd = nav / nav.cummax() - 1.0
    monthly = nav.resample("ME").last().pct_change().dropna()
    yearly = nav.resample("YE").last().pct_change().dropna()
    row = {
        "strategy": name,
        "max_drawdown": float(dd.min()),
        "trough_date": str(ep.loc[ep["depth"].idxmin(), "trough"].date()),
        "longest_underwater_days": int(ep["underwater_days"].max()),
        "longest_underwater_years": round(float(ep["underwater_days"].max()) / 365.25, 2),
        "longest_trough_to_recovery_days": float(ep["trough_to_recovery_days"].max()),
        "days_below_minus10": float((dd <= -0.10).mean()),
        "days_below_minus20": float((dd <= -0.20).mean()),
        "episodes_10_plus": int((ep["depth"] <= -0.10).sum()),
        "episodes_20_plus": int((ep["depth"] <= -0.20).sum()),
        "rms_drawdown": float(np.sqrt((dd ** 2).mean())),
        "negative_months_share": float((monthly < 0).mean()),
        "worst_month": float(monthly.min()),
        "worst_month_label": str(monthly.idxmin().date()),
        "negative_years": int((yearly < 0).sum()),
        "years": len(yearly),
        "worst_year": float(yearly.min()),
        "worst_year_label": int(yearly.idxmin().year),
        "final_multiple": float(nav.iloc[-1] / nav.iloc[0]),
    }
    for years in (1, 3, 5, 10):
        share, worst = window_loss_share(nav, years)
        row[f"share_{years}y_losing"] = share
        row[f"worst_{years}y_annualized"] = worst
    return row


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nav = pd.read_csv(SRC / "nav_daily.csv", index_col=0, parse_dates=True)
    rows, eps = [], []
    for name in STRATEGIES:
        series = nav[name].dropna()
        ep = episodes(series)
        rows.append(experience_row(name, series, ep))
        ep.insert(0, "strategy", name)
        eps.append(ep)
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "holding_experience.csv", index=False)
    pd.concat(eps).sort_values(["strategy", "depth"]).to_csv(OUT / "episodes.csv", index=False)

    dca = pd.read_csv(SRC / "dca_summary.csv").set_index("strategy")
    full = pd.read_csv(SRC / "dca_full_path.csv").set_index("strategy")
    dca_rows = []
    for name in STRATEGIES:
        dca_rows.append({"strategy": name,
                         "full_path_xirr": float(full.loc[name, "xirr"]),
                         "full_path_terminal_per_unit": float(full.loc[name, "terminal_per_contributed"]),
                         "full_path_max_float_loss": float(full.loc[name, "max_float_loss"]),
                         "window_median_xirr": float(dca.loc[name, "median_xirr"]),
                         "window_worst_xirr": float(dca.loc[name, "worst_xirr"])})
    pd.DataFrame(dca_rows).to_csv(OUT / "dca_experience.csv", index=False)

    pd.set_option("display.width", 220)
    print(summary.round(3).T.to_string())
    print(pd.DataFrame(dca_rows).round(3).to_string())


if __name__ == "__main__":
    main()
