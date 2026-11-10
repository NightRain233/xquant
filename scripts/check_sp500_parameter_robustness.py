"""Magic-parameter check for S2 (half trend) and VT-1.0 (15% vol target) on the 2026-11-10 S&P 500 window.

Run (from repo root, after ``scripts/fetch_sp500_enhance_data.py``):
  uv run python -I scripts/check_sp500_parameter_robustness.py

A parameter is "magic" when only one point of the grid passes. The grids below are fixed here before any
result is seen and contain the frozen default. A cell passes when its Sharpe and its Calmar both beat buy-and-hold
over the same window. The check reports the pass share of the grid and whether the frozen default sits inside a
passing neighborhood. Nothing is selected from the grid.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import research_sp500_enhance_vs_dca as R  # noqa: E402
from xquant import overlay_rules as ov  # noqa: E402
from xquant import position_rules as pr  # noqa: E402

OUT = ROOT / "outputs" / "magic-param-check-2026-11-10"
SEGMENTS = {"main": (R.MAIN_START, R.END), "2000-2012": (R.MAIN_START, "2012-12-31"), "2013-2026": ("2013-01-01", R.END)}

S2_MA_WEEKS = (20, 25, 30, 35, 40)
S2_OFF_LEVEL = (0.0, 0.25, 0.5, 0.75)
S2_SLOPE_WEEKS = (2, 4, 8)
VT_TARGET = (0.10, 0.125, 0.15, 0.175, 0.20)
VT_WINDOW = (10, 21, 42, 63)
VT_BAND = (0.05, 0.10, 0.20)


def run_signal(data: ov.MarketData, signal_fn, start: str) -> ov.EngineResult:
    start_i = int(data.dates.searchsorted(pd.Timestamp(start)))
    prices = pd.DataFrame({"a": data.spy.to_numpy(float), "b": data.bond.to_numpy(float)}, index=data.dates)
    return ov.run_overlay(prices, signal_fn(start_i), start_i, R.COST, data.cash_pos, data.cash_neg)


def metrics_row(data: ov.MarketData, res: ov.EngineResult) -> dict:
    row = {}
    for name, (start, end) in SEGMENTS.items():
        m = R.window_metrics(res, start, end)
        row[f"{name}_cagr"] = m["cagr"]
        row[f"{name}_sharpe"] = m["sharpe"]
        row[f"{name}_calmar"] = m["calmar"]
        row[f"{name}_max_dd"] = m["max_dd"]
    row["trades_per_year"] = ov.count_trades(res) / ((pd.Timestamp(R.END) - pd.Timestamp(R.MAIN_START)).days / 365.25)
    return row


def add_vs_b0(df: pd.DataFrame, b0: dict) -> pd.DataFrame:
    for name in SEGMENTS:
        df[f"{name}_pass"] = (df[f"{name}_sharpe"] > b0[f"{name}_sharpe"]) & (df[f"{name}_calmar"] > b0[f"{name}_calmar"])
    return df


def s2_signal_factory(data: ov.MarketData, ma_weeks: int, slope_weeks: int, off: float):
    states = pr.stage_states(data.spy, ma_weeks=ma_weeks, slope_weeks=slope_weeks)
    return lambda start_i: ov._dict_adapter(pr.rule_stage_blend(states, data.dates, start_i, on=1.0, off=off))


def vt_signal_factory(data: ov.MarketData, target: float, window: int, band: float):
    return lambda start_i: ov.vol_target_band(data.spy, start_i, target=target, cap=1.0, window=window, band=band)


def s2_grid(data: ov.MarketData, b0: dict) -> pd.DataFrame:
    cells = [(m, 4, o) for m in S2_MA_WEEKS for o in S2_OFF_LEVEL]
    cells += [(30, s, 0.5) for s in S2_SLOPE_WEEKS if s != 4]
    rows = []
    for ma, slope, off in cells:
        res = run_signal(data, s2_signal_factory(data, ma, slope, off), R.MAIN_START)
        rows.append({"rule": "S2", "ma_weeks": ma, "slope_weeks": slope, "off_weight": off,
                     "is_default": (ma, slope, off) == (30, 4, 0.5), **metrics_row(data, res)})
    return add_vs_b0(pd.DataFrame(rows), b0)


def vt_grid(data: ov.MarketData, b0: dict) -> pd.DataFrame:
    cells = [(t, w, 0.10) for t in VT_TARGET for w in VT_WINDOW]
    cells += [(0.15, 21, b) for b in VT_BAND if b != 0.10]
    rows = []
    for target, window, band in cells:
        res = run_signal(data, vt_signal_factory(data, target, window, band), R.MAIN_START)
        rows.append({"rule": "VT-1.0", "target": target, "vol_window": window, "band": band,
                     "is_default": (target, window, band) == (0.15, 21, 0.10), **metrics_row(data, res)})
    return add_vs_b0(pd.DataFrame(rows), b0)


def selfcheck(data: ov.MarketData, b0: dict, s2_default: pd.Series, vt_default: pd.Series) -> dict:
    """The default cells must reproduce the study's frozen numbers (S2 0.532 / 0.262, VT-1.0 0.478 / 0.176)."""
    out = {}
    for name, row, sharpe, calmar in (("S2", s2_default, 0.532, 0.262), ("VT-1.0", vt_default, 0.478, 0.176)):
        out[name] = {"main_sharpe": float(row["main_sharpe"]), "expected_sharpe": sharpe,
                     "main_calmar": float(row["main_calmar"]), "expected_calmar": calmar,
                     "ok": bool(abs(row["main_sharpe"] - sharpe) < 5e-4 and abs(row["main_calmar"] - calmar) < 5e-4)}
    out["b0_main_sharpe"] = b0["main_sharpe"]
    return out


def neighborhood(df: pd.DataFrame, default_mask: pd.Series, keys: list[str]) -> dict:
    """Passing share among the default's grid neighbors (one step on each axis) and the default itself."""
    d = df[default_mask].iloc[0]
    grid = df.set_index(keys)
    near = []
    for k in keys:
        values = sorted(df[k].unique())
        i = values.index(d[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(values):
                probe = {kk: d[kk] for kk in keys}
                probe[k] = values[j]
                key = tuple(probe[kk] for kk in keys)
                if key in grid.index:
                    near.append(bool(grid.loc[key, "main_pass"]))
    return {"neighbors_checked": len(near), "neighbors_passing": int(sum(near)), "default_passes": bool(d["main_pass"])}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data, _bill, _validation = R.main_universe()
    b0_res = ov.simulate(data, "B0", R.MAIN_START)
    b0 = metrics_row(data, b0_res)

    s2 = s2_grid(data, b0)
    vt = vt_grid(data, b0)
    s2.to_csv(OUT / "s2_grid.csv", index=False)
    vt.to_csv(OUT / "vt_grid.csv", index=False)

    s2_default = s2[s2["is_default"]].iloc[0]
    vt_default = vt[vt["is_default"]].iloc[0]
    summary = {
        "selfcheck": selfcheck(data, b0, s2_default, vt_default),
        "b0": {k: float(v) for k, v in b0.items()},
        "s2": {"cells": len(s2), "main_pass_share": float(s2["main_pass"].mean()),
               "segment_pass_share": {n: float(s2[f"{n}_pass"].mean()) for n in SEGMENTS},
               "neighborhood": neighborhood(s2[s2["slope_weeks"] == 4], s2["is_default"][s2["slope_weeks"] == 4], ["ma_weeks", "off_weight"])},
        "vt": {"cells": len(vt), "main_pass_share": float(vt["main_pass"].mean()),
               "segment_pass_share": {n: float(vt[f"{n}_pass"].mean()) for n in SEGMENTS},
               "neighborhood": neighborhood(vt[vt["band"] == 0.10], vt["is_default"][vt["band"] == 0.10], ["target", "vol_window"])},
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))

    show = ["ma_weeks", "slope_weeks", "off_weight", "main_sharpe", "main_calmar", "main_max_dd", "main_cagr",
            "2000-2012_pass", "2013-2026_pass", "main_pass", "is_default"]
    print("B0 main sharpe/calmar:", round(b0["main_sharpe"], 3), round(b0["main_calmar"], 3))
    print(json.dumps(summary["selfcheck"], indent=1))
    print(s2[show].round(3).to_string())
    show_vt = ["target", "vol_window", "band", "main_sharpe", "main_calmar", "main_max_dd", "main_cagr",
               "2000-2012_pass", "2013-2026_pass", "main_pass", "is_default"]
    print(vt[show_vt].round(3).to_string())
    print(json.dumps({"s2": summary["s2"], "vt": summary["vt"]}, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
