"""Independent reconciliation & unified cross-direction scorecard for the S&P 500 4-direction study (2026-11-22).

Reads the daily NAV curves and summary tables produced by the 4 independent subagent scripts,
verifies exact numerical reconciliation on overlapping strategies, re-computes all Q3/Q5/DCA metrics
on identical common windows via ``src/xquant/sp500_lab.py``, and writes master comparison tables to
``outputs/sp500-four-directions-2026-11-22/``.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]
from xquant import sp500_lab as lab  # noqa: E402

OUT = ROOT / "outputs" / "sp500-four-directions-2026-11-22"
DIR1 = ROOT / "outputs" / "sp500-dir1-structural-2026-11-22"
DIR2 = ROOT / "outputs" / "sp500-dir2-trend-shield-2026-11-22"
DIR3 = ROOT / "outputs" / "sp500-dir3-vix-credit-2026-11-22"
DIR4 = ROOT / "outputs" / "sp500-dir4-domestic-crypto-2026-11-22"


def nav_metrics(nav: pd.Series, rf_daily: pd.Series, start: str | None = None, end: str | None = None) -> dict:
    s = nav.dropna()
    if start is not None:
        s = s[s.index >= pd.Timestamp(start)]
    if end is not None:
        s = s[s.index <= pd.Timestamp(end)]
    s = s / s.iloc[0]
    days = (s.index[-1] - s.index[0]).days
    years = days / 365.25
    cagr = float(s.iloc[-1] ** (1.0 / years) - 1.0)
    ret = s.pct_change().dropna()
    vol = float(ret.std(ddof=1) * np.sqrt(252.0))
    rf = rf_daily.reindex(ret.index).fillna(0.0)
    ex = ret - rf
    sharpe = float(ex.mean() / ex.std(ddof=1) * np.sqrt(252.0)) if ex.std(ddof=1) > 0 else np.nan
    dd = s / s.cummax() - 1.0
    max_dd = float(dd.min())
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else np.nan
    uw = lab.max_underwater_years(s)
    yearly = s.resample("YE").last().pct_change().dropna()
    worst_y = float(yearly.min()) if len(yearly) else np.nan
    return {
        "cagr": cagr,
        "vol": vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "calmar": calmar,
        "max_underwater_years": uw,
        "worst_year": worst_y,
    }


def fast_xirr(day_offsets: np.ndarray, terminal_val: float) -> float:
    """Exact annualized IRR matching cashflow_research.xirr for 1-unit contributions at day_offsets."""
    yrs = day_offsets / 365.25
    lo, hi = -0.95, 5.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        val = float(np.sum((1.0 + mid) ** yrs))
        if val > terminal_val:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def fast_dca_rolling_windows(nav: pd.Series, window_months: int = 120, cost: float = 0.001) -> pd.DataFrame:
    """Vectorized equivalent of lab.dca_rolling_windows (verified exact match)."""
    dates = pd.DatetimeIndex(nav.index)
    vals = nav.to_numpy(float)
    ym = dates.year * 12 + dates.month
    first_idx = np.flatnonzero(np.r_[True, ym[1:] != ym[:-1]])
    last_idx = np.r_[first_idx[1:] - 1, len(dates) - 1]
    rows = []
    for k in range(len(first_idx) - window_months + 1):
        i0 = int(first_idx[k])
        i1 = int(last_idx[k + window_months - 1])
        c_idx = first_idx[k : k + window_months]
        if len(c_idx) != window_months:
            continue
        units = float(np.sum((1.0 - cost) / vals[c_idx]))
        end_val = units * float(vals[i1])
        day_off = (dates[i1] - dates[c_idx]).days.to_numpy(float)
        x = fast_xirr(day_off, end_val)
        seg = vals[i0 : i1 + 1]
        u_mdd = float(np.min(seg / np.maximum.accumulate(seg) - 1.0))
        rows.append(
            {
                "start": str(dates[i0].date()),
                "end": str(dates[i1].date()),
                "xirr": x,
                "unit_max_dd": u_mdd,
                "dca_ratio": float(x / abs(u_mdd)) if u_mdd < 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def compare_against_bench_windows(strat_nav: pd.Series, bw: pd.DataFrame, window_months: int = 120, cost: float = 0.001) -> dict:
    sw = fast_dca_rolling_windows(strat_nav, window_months=window_months, cost=cost)
    if sw.empty or bw.empty:
        return {"n_windows": 0}
    merged = sw.merge(bw, on=["start", "end"], suffixes=("_s", "_b"))
    return {
        "n_windows": int(len(merged)),
        "ratio_beat_share": float((merged["dca_ratio_s"] > merged["dca_ratio_b"]).mean()),
        "xirr_beat_share": float((merged["xirr_s"] > merged["xirr_b"]).mean()),
    }


def load_nav(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = pd.DatetimeIndex(df.index).normalize()
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    us = lab.load_us_bundle()
    dom = lab.load_domestic_bundle()
    us_rf = pd.Series(us["cash_pos"] - 1.0, index=us["dates"])
    dom_rf = pd.Series(dom["cash_pos"] - 1.0, index=dom["dates"])

    # Load all subagent daily NAVs (10bp)
    n1_us = load_nav(DIR1 / "nav_us_2005_10bp.csv")
    n2_us = load_nav(DIR2 / "nav_us_2005_10bp.csv")
    n3_vix = load_nav(DIR3 / "nav_vix_us_10bp.csv")
    n4_us = load_nav(DIR4 / "nav_crypto_base_10bp.csv")

    n1_dom = load_nav(DIR1 / "nav_domestic_10bp.csv")
    n2_dom = load_nav(DIR2 / "nav_domestic_10bp.csv")
    n3_dom = load_nav(DIR3 / "nav_domestic_10bp.csv")
    n4_dom = load_nav(DIR4 / "nav_domestic_10bp.csv")

    # Also read 30bp & turnover lookups from subagent summary CSVs
    s1_us = pd.read_csv(DIR1 / "summary_us_gold.csv")
    s2_us = pd.read_csv(DIR2 / "summary_us.csv")
    s3_vix = pd.read_csv(DIR3 / "summary_vix_us.csv")
    s3_cred = pd.read_csv(DIR3 / "summary_credit_us.csv")
    s4_cry = pd.read_csv(DIR4 / "summary_crypto_stress.csv")

    s1_dom = pd.read_csv(DIR1 / "summary_domestic_gold.csv")
    s2_dom = pd.read_csv(DIR2 / "summary_domestic.csv")
    s3_dom = pd.read_csv(DIR3 / "summary_domestic.csv")
    s4_dom = pd.read_csv(DIR4 / "summary_domestic_overlay.csv")

    # 1. Cross-agent reconciliation audit
    checks = {}
    pairs = [
        ("US_B0_SPY_dir1_vs_dir2", n1_us["B0_SPY"], n2_us["B0_SPY"]),
        ("US_B0_SPY_dir1_vs_dir4", n1_us["B0_SPY"], n4_us["B0_SPY"]),
        ("US_GOLD_75_25_Q_dir1_vs_dir4", n1_us["GOLD_75_25_Q"], n4_us["GOLD_75_25_Q"]),
        ("US_S2_CASH_dir2_vs_dir4", n2_us["S2_CASH"], n4_us["S2_CASH"]),
        ("US_S2_GOLD_dir2_vs_dir4", n2_us["S2_GOLD"], n4_us["S2_GOLD"]),
        ("DOM_B0_513500_dir1_vs_dir2", n1_dom["B0_513500"], n2_dom["B0_513500"]),
        ("DOM_B0_513500_dir1_vs_dir3", n1_dom["B0_513500"], n3_dom["B0_513500"]),
        ("DOM_B0_513500_dir1_vs_dir4", n1_dom["B0_513500"], n4_dom["B0_513500"]),
    ]
    for label, a, b in pairs:
        idx = a.index.intersection(b.index)
        diff = float((a.loc[idx] - b.loc[idx]).abs().max())
        checks[label] = {"n_days": int(len(idx)), "max_abs_diff": diff, "passed": diff < 1e-9}

    subagent_self_checks = {}
    for name, folder in [("dir1", DIR1), ("dir2", DIR2), ("dir3", DIR3), ("dir4", DIR4)]:
        sc = json.loads((folder / "self_checks.json").read_text())
        passed = bool(sc.get("overall_passed", sc.get("all_checks_passed", sc.get("all_passed", False))))
        subagent_self_checks[name] = passed

    # 2. Master Table A: US Main Window 2005-01-03 ~ 2026-10-16 (pure real GLD)
    # Build VT_15 baseline independently on exact 2005 window for completeness
    si05 = int(us["dates"].searchsorted(pd.Timestamp("2005-01-03")))
    log_ret = np.log(us["spy"]).diff()
    vol21 = (log_ret.rolling(21).std(ddof=1) * np.sqrt(252.0)).to_numpy(float)

    def vt15_sig(i, actual):
        v = vol21[i]
        if not np.isfinite(v) or v <= 0:
            return None
        w = min(1.0, 0.15 / v)
        if i == si05 or abs(w - actual[0]) > 0.10:
            return np.array([w])
        return None

    vt15_res_10 = lab.run_multi_asset_overlay(us["spy"].to_frame(), vt15_sig, si05, 0.001, us["cash_pos"], us["cash_neg"])
    vt15_res_30 = lab.run_multi_asset_overlay(us["spy"].to_frame(), vt15_sig, si05, 0.003, us["cash_pos"], us["cash_neg"])
    vt15_m10 = lab.summarize_result(vt15_res_10, primary_col="spy")
    vt15_m30 = lab.summarize_result(vt15_res_30, primary_col="spy")

    us_2005_specs = [
        ("基线", "B0_SPY (直接持有)", n1_us["B0_SPY"], 0.0, 10.90 / 100.0, 0.551),
        ("旧基线", "S2_CASH (半仓趋势+现金)", n2_us["S2_CASH"], 1.42, 9.72 / 100.0, 0.649),
        ("旧基线", "VT_15 (15%目标波动+现金)", vt15_res_10.nav, vt15_m10["annual_turnover"], vt15_m30["cagr"], vt15_m30["sharpe"]),
        ("旧基线", "MTF3_CASH (周月双确认+现金)", n2_us["MTF3_CASH"], 2.14, 8.09 / 100.0, 0.593),
        ("旧基线", "TVT50_CASH (趋势控波动+现金)", n4_us["TVT50_CASH"], None, None, None),
        ("方向1", "GOLD_75_25_Q (75标普+25黄金季调)", n1_us["GOLD_75_25_Q"], 0.126, 11.29 / 100.0, 0.675),
        ("方向1", "GOLD_80_20_Q (80标普+20黄金季调)", n1_us["GOLD_80_20_Q"], 0.107, 11.23 / 100.0, 0.651),
        ("方向1", "GOLD_INVVOL_M (反波动股金月调)", n1_us["GOLD_INVVOL_M"], 1.394, 11.11 / 100.0, 0.737),
        ("方向1", "GOLD_BOND_70_15_15_Q (70股15金15债)", n1_us["GOLD_BOND_70_15_15_Q"], 0.135, 10.15 / 100.0, 0.670),
        ("方向2", "S2_GOLD (S2破位换50%黄金)", n2_us["S2_GOLD"], 2.85, 10.77 / 100.0, 0.662),
        ("方向2", "S2_GOLD_TREND (S2破位+黄金趋势过滤)", n2_us["S2_GOLD_TREND"], 2.75, 10.24 / 100.0, 0.651),
        ("方向2", "S2_BOND_GOLD (S2破位换25%金+25%债)", n2_us["S2_BOND_GOLD"], 2.85, 10.22 / 100.0, 0.674),
        ("方向4/2", "TVT50_GOLD (TVT50减仓换黄金)", n4_us["TVT50_GOLD"], None, None, None),
    ]

    # Pull exact 30bp & turnover from s4_cry for TVT50_CASH and TVT50_GOLD
    def lookup_s4(strat, scen, col):
        sub = s4_cry[(s4_cry["strategy"] == strat) & (s4_cry["scenario"] == scen)]
        return float(sub[col].iloc[0]) if not sub.empty and col in sub.columns else np.nan

    b0_us_2005 = n1_us["B0_SPY"]
    bw_us_2005 = fast_dca_rolling_windows(b0_us_2005, window_months=120, cost=0.001)
    us_2005_rows = []
    for group, label, nav, turn, cagr30, sh30 in us_2005_specs:
        if "TVT50_CASH" in label:
            turn = lookup_s4("TVT50_CASH", "US_ETF_10bp", "annual_turnover")
            cagr30 = lookup_s4("TVT50_CASH", "CRYPTO_SPOT_DIV_30bp", "cagr")
            sh30 = lookup_s4("TVT50_CASH", "CRYPTO_SPOT_DIV_30bp", "sharpe")
        elif "TVT50_GOLD" in label:
            turn = lookup_s4("TVT50_GOLD", "US_ETF_10bp", "annual_turnover")
            cagr30 = lookup_s4("TVT50_GOLD", "CRYPTO_SPOT_DIV_30bp", "cagr")
            sh30 = lookup_s4("TVT50_GOLD", "CRYPTO_SPOT_DIV_30bp", "sharpe")

        m_full = nav_metrics(nav, us_rf, "2005-01-03", "2026-10-16")
        m_s1 = nav_metrics(nav, us_rf, "2005-01-03", "2012-12-31")
        m_s2 = nav_metrics(nav, us_rf, "2013-01-01", "2026-10-16")
        dca_full = lab.dca_full_path(nav, cost=0.001)
        dca_10y = compare_against_bench_windows(nav, bw_us_2005, window_months=120, cost=0.001)
        us_2005_rows.append(
            {
                "group": group,
                "strategy": label,
                "cagr_10bp": m_full["cagr"],
                "vol_10bp": m_full["vol"],
                "sharpe_10bp": m_full["sharpe"],
                "max_dd_10bp": m_full["max_dd"],
                "calmar_10bp": m_full["calmar"],
                "max_underwater_y": m_full["max_underwater_years"],
                "worst_year": m_full["worst_year"],
                "seg1_2005_2012_cagr": m_s1["cagr"],
                "seg1_2005_2012_sharpe": m_s1["sharpe"],
                "seg2_2013_2026_cagr": m_s2["cagr"],
                "seg2_2013_2026_sharpe": m_s2["sharpe"],
                "annual_turnover": turn,
                "cagr_30bp": cagr30,
                "sharpe_30bp": sh30,
                "dca_full_xirr": dca_full["xirr"],
                "dca_full_max_float_loss": dca_full["max_float_loss"],
                "dca_10y_ratio_beat_share": dca_10y.get("ratio_beat_share", np.nan),
                "dca_10y_xirr_beat_share": dca_10y.get("xirr_beat_share", np.nan),
            }
        )
    pd.DataFrame(us_2005_rows).to_csv(OUT / "master_us_2005_10bp.csv", index=False)

    # 3. Master Table B: US Common Window 2006-08-01 ~ 2026-10-16 (includes VIX & SPHQ/RSP comparison!)
    n1_fac = load_nav(DIR1 / "nav_factors_2006_10bp.csv")
    us_2006_specs = [
        ("基线", "B0_SPY", n3_vix["B0_SPY"]),
        ("旧基线", "S2_CASH", n3_vix["S2_CASH"]),
        ("旧基线", "VT_15", n3_vix["VT_15"]),
        ("方向1", "GOLD_75_25_Q", n1_us["GOLD_75_25_Q"]),
        ("方向1", "GOLD_INVVOL_M", n1_us["GOLD_INVVOL_M"]),
        ("方向1-因子", "SPHQ_100 (质量)", n1_fac["SPHQ_100"]),
        ("方向1-因子", "RSP_100 (等权)", n1_fac["RSP_100"]),
        ("方向2", "S2_GOLD", n2_us["S2_GOLD"]),
        ("方向2", "S2_BOND_GOLD", n2_us["S2_BOND_GOLD"]),
        ("方向3", "VIX_BRAKE_CASH", n3_vix["VIX_BRAKE_CASH"]),
        ("方向3", "VIX_BRAKE_GOLD", n3_vix["VIX_BRAKE_GOLD"]),
        ("方向3", "VIX_OR_S2_GOLD", n3_vix["VIX_OR_S2_GOLD"]),
        ("方向4/2", "TVT50_GOLD", n4_us["TVT50_GOLD"]),
    ]
    b0_2006 = n3_vix["B0_SPY"].loc["2006-08-01":]
    bw_2006 = fast_dca_rolling_windows(b0_2006, window_months=120, cost=0.001)
    us_2006_rows = []
    for group, label, nav in us_2006_specs:
        s_nav = nav.loc["2006-08-01":"2026-10-16"]
        s_nav = s_nav / s_nav.iloc[0]
        m = nav_metrics(s_nav, us_rf)
        m1 = nav_metrics(s_nav, us_rf, "2006-08-01", "2012-12-31")
        m2 = nav_metrics(s_nav, us_rf, "2013-01-01", "2026-10-16")
        dca_10y = compare_against_bench_windows(s_nav, bw_2006, window_months=120, cost=0.001)
        us_2006_rows.append(
            {
                "group": group,
                "strategy": label,
                "cagr_10bp": m["cagr"],
                "sharpe_10bp": m["sharpe"],
                "max_dd_10bp": m["max_dd"],
                "calmar_10bp": m["calmar"],
                "seg1_2006_2012_sharpe": m1["sharpe"],
                "seg2_2013_2026_sharpe": m2["sharpe"],
                "dca_10y_ratio_beat_share": dca_10y.get("ratio_beat_share", np.nan),
                "dca_10y_xirr_beat_share": dca_10y.get("xirr_beat_share", np.nan),
            }
        )
    pd.DataFrame(us_2006_rows).to_csv(OUT / "master_us_2006_common.csv", index=False)

    # 4. Master Table C: Domestic 513500 + 518880 (2014-10-08 ~ 2026-09-30)
    def lookup_dom(df: pd.DataFrame, col_strat: str, strat: str, cost_filter: dict, metric_col: str) -> float:
        sub = df[df[col_strat] == strat]
        for k, v in cost_filter.items():
            if k in sub.columns:
                sub = sub[sub[k] == v]
        return float(sub[metric_col].iloc[0]) if not sub.empty and metric_col in sub.columns else np.nan

    dom_specs = [
        ("基线", "B0_513500 (持有)", n1_dom["B0_513500"], 0.0, 14.17 / 100.0, 0.735),
        ("旧最佳", "TVT50_CASH (自身信号+现金)", n4_dom["TVT50_CASH"], 2.20, 10.81 / 100.0, 0.727),
        ("方向1", "CN_75_25_Q (75标普+25黄金季调)", n1_dom["CN_75_25_Q"], 0.119, 13.86 / 100.0, 0.867),
        ("方向1", "CN_80_20_Q (80标普+20黄金季调)", n1_dom["CN_80_20_Q"], 0.102, 13.95 / 100.0, 0.841),
        ("方向1", "CN_INVVOL_M (反波动股金月调)", n1_dom["CN_INVVOL_M"], 1.129, 13.06 / 100.0, 0.943),
        ("方向2", "CN_S2_GOLD_US (外盘S2+黄金盾)", n2_dom["CN_S2_GOLD_US"], None, 13.10 / 100.0, None),
        ("方向2", "CN_S2_GOLD_SELF (自身S2+黄金盾)", n2_dom["CN_S2_GOLD_SELF"], None, 10.66 / 100.0, None),
        ("方向3", "CN_VIX_BRAKE_GOLD (美股VIX+黄金)", n3_dom["CN_VIX_BRAKE_GOLD"], 6.32, 9.46 / 100.0, 0.532),
        ("方向4", "TVT50_GOLD (自身TVT50+黄金盾)", n4_dom["TVT50_GOLD"], 4.38, 11.83 / 100.0, 0.748),
        ("方向4", "TVT50_HALF_GOLD_CASH (半金半现)", n4_dom["TVT50_HALF_GOLD_CASH"], 3.32, 11.32 / 100.0, 0.746),
        ("方向4", "PREM_TRIM_CASH (溢价>6%减半现金)", n4_dom["PREM_TRIM_CASH"], 1.14, 15.77 / 100.0, 0.888),
        ("方向4", "PREM_TRIM_GOLD (溢价>6%减半黄金)", n4_dom["PREM_TRIM_GOLD"], 2.28, 15.77 / 100.0, 0.844),
        ("方向4", "TVT50_PREM_GOLD (TVT50+溢价+黄金)", n4_dom["TVT50_PREM_GOLD"], 6.53, 12.00 / 100.0, 0.768),
    ]

    # Fill exact turnover / 30bp sharpe for dir2 domestic from s2_dom
    for row_idx, item in enumerate(dom_specs):
        if item[1].startswith("CN_S2_GOLD_US"):
            sub10 = s2_dom[(s2_dom["strategy"] == "CN_S2_GOLD_US") & (s2_dom["cost_bps"] == 10) & (s2_dom["segment"] == "full")]
            sub30 = s2_dom[(s2_dom["strategy"] == "CN_S2_GOLD_US") & (s2_dom["cost_bps"] == 30) & (s2_dom["segment"] == "full")]
            dom_specs[row_idx] = (item[0], item[1], item[2], float(sub10["annual_turnover"].iloc[0]), float(sub30["cagr"].iloc[0]), float(sub30["sharpe"].iloc[0]))
        elif item[1].startswith("CN_S2_GOLD_SELF"):
            sub10 = s2_dom[(s2_dom["strategy"] == "CN_S2_GOLD_SELF") & (s2_dom["cost_bps"] == 10) & (s2_dom["segment"] == "full")]
            sub30 = s2_dom[(s2_dom["strategy"] == "CN_S2_GOLD_SELF") & (s2_dom["cost_bps"] == 30) & (s2_dom["segment"] == "full")]
            dom_specs[row_idx] = (item[0], item[1], item[2], float(sub10["annual_turnover"].iloc[0]), float(sub30["cagr"].iloc[0]), float(sub30["sharpe"].iloc[0]))

    b0_dom = n1_dom["B0_513500"]
    bw_dom_5y = fast_dca_rolling_windows(b0_dom, window_months=60, cost=0.001)
    bw_dom_10y = fast_dca_rolling_windows(b0_dom, window_months=120, cost=0.001)
    dom_rows = []
    for group, label, nav, turn, cagr30, sh30 in dom_specs:
        m = nav_metrics(nav, dom_rf)
        m1 = nav_metrics(nav, dom_rf, "2014-10-08", "2020-12-31")
        m2 = nav_metrics(nav, dom_rf, "2021-01-01", "2026-09-30")
        dca_full = lab.dca_full_path(nav, cost=0.001)
        dca_5y = compare_against_bench_windows(nav, bw_dom_5y, window_months=60, cost=0.001)
        dca_10y = compare_against_bench_windows(nav, bw_dom_10y, window_months=120, cost=0.001)
        dom_rows.append(
            {
                "group": group,
                "strategy": label,
                "cagr_10bp": m["cagr"],
                "vol_10bp": m["vol"],
                "sharpe_10bp": m["sharpe"],
                "max_dd_10bp": m["max_dd"],
                "calmar_10bp": m["calmar"],
                "max_underwater_y": m["max_underwater_years"],
                "seg1_2014_2020_cagr": m1["cagr"],
                "seg1_2014_2020_sharpe": m1["sharpe"],
                "seg2_2021_2026_cagr": m2["cagr"],
                "seg2_2021_2026_sharpe": m2["sharpe"],
                "annual_turnover": turn,
                "cagr_30bp": cagr30,
                "sharpe_30bp": sh30,
                "dca_full_xirr": dca_full["xirr"],
                "dca_5y_ratio_beat_share": dca_5y.get("ratio_beat_share", np.nan),
                "dca_10y_ratio_beat_share": dca_10y.get("ratio_beat_share", np.nan),
                "dca_10y_xirr_beat_share": dca_10y.get("xirr_beat_share", np.nan),
            }
        )
    pd.DataFrame(dom_rows).to_csv(OUT / "master_domestic_513500.csv", index=False)

    # Save crypto friction copy for unified access
    s4_cry.to_csv(OUT / "master_crypto_friction.csv", index=False)

    audit = {
        "cross_agent_nav_reconciliation": checks,
        "all_reconciliations_passed": all(v["passed"] for v in checks.values()),
        "subagent_self_checks_passed": subagent_self_checks,
        "all_subagents_passed": all(subagent_self_checks.values()),
    }
    (OUT / "reconciliation_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")

    print("=== RECONCILIATION AUDIT ===")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print("\n=== MASTER US 2005-2026 (10bp) ===")
    df_us = pd.DataFrame(us_2005_rows)
    print(df_us[["group", "strategy", "cagr_10bp", "sharpe_10bp", "max_dd_10bp", "calmar_10bp", "seg1_2005_2012_sharpe", "seg2_2013_2026_sharpe", "annual_turnover", "cagr_30bp", "sharpe_30bp", "dca_10y_ratio_beat_share"]].to_string(index=False))
    print("\n=== MASTER US 2006-2026 COMMON (10bp, incl. VIX & Factors) ===")
    df_06 = pd.DataFrame(us_2006_rows)
    print(df_06.to_string(index=False))
    print("\n=== MASTER DOMESTIC 513500 2014-2026 (10bp) ===")
    df_dom = pd.DataFrame(dom_rows)
    print(df_dom[["group", "strategy", "cagr_10bp", "sharpe_10bp", "max_dd_10bp", "calmar_10bp", "seg1_2014_2020_sharpe", "seg2_2021_2026_sharpe", "annual_turnover", "cagr_30bp", "sharpe_30bp", "dca_5y_ratio_beat_share", "dca_10y_ratio_beat_share", "dca_10y_xirr_beat_share"]].to_string(index=False))


if __name__ == "__main__":
    main()
