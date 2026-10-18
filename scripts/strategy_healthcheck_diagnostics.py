"""Audit source revisions, legacy timing, and the frozen BTC proxy limitations."""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from review_frozen_strategies import ROOT, CORE, dump, load_market, btc_targets, replay, summarize, get_strategy
from datetime import datetime
from zoneinfo import ZoneInfo


def legacy_timing_evidence():
    path = ROOT/"research/notebooks/q10-live-readiness-stress-practice.ipynb"
    notebook = json.loads(path.read_text())
    definition = None
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if "def backtest_targets(" not in source:
            continue
        definition = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "backtest_targets")
    if definition is None:
        raise ValueError("Frozen Q10 function not found")
    dates = pd.date_range("2026-09-07", periods=4)
    symbols = ("ASSET",)
    close = pd.DataFrame({"ASSET": [100.,100.,150.,150.]}, index=dates)
    targets = pd.DataFrame({"ASSET": [0.,1.,1.,1.], "CASH": [1.,0.,0.,0.]}, index=dates)
    namespace = {"pd": pd, "np": np, "close": close, "ALL_SYMBOLS": symbols, "INITIAL_CAPITAL": 100.}
    module = ast.Module(body=[definition], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    returns = close.pct_change().fillna(0)
    result = namespace["backtest_targets"]("timing_probe", targets, returns, returns, returns*0, execution="next_close")
    observed = float(result["nav"].iloc[2])
    if observed != 150.:
        raise AssertionError("Legacy timing behavior changed; reassess the finding")
    return {"notebook": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "case": "Signal at D close, price rises 100 to 150 before D+1 close, then flat; zero costs",
            "legacy_label": "next_close", "legacy_nav_at_execution_close": observed,
            "true_next_close_nav_at_execution_close": 100.,
            "finding": "New weights receive the D-to-D+1 close return before the stated D+1 close fill. Also weights are reset daily without drift-based turnover.",
            "scope": "Frozen Q10 notebook evidence, not a claim that the current trading execution kernel has this defect."}


def source_overlap(snapshot, out):
    archive = ROOT/"research/trading-ledger-2026-09-05/core90_recovery_2026_09_05/original_xquant.zip"
    rows = []
    with zipfile.ZipFile(archive) as bundle:
        names = {Path(n).stem: n for n in bundle.namelist() if "market_data/" in n and n.endswith(".parquet") and "_weekly" not in n}
        for path in sorted(snapshot.glob("*.parquet")):
            fresh = pd.read_parquet(path)
            row = {"symbol": path.stem, "first": str(fresh.index.min().date()), "last": str(fresh.index.max().date()),
                   "rows": len(fresh), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "nonpositive_close": int((fresh.Close<=0).sum()), "duplicate_dates": int(fresh.index.duplicated().sum())}
            if path.stem in names:
                old = pd.read_parquet(io.BytesIO(bundle.read(names[path.stem])))
                old.index = pd.DatetimeIndex(old.index).tz_localize(None).normalize()
                dates = old.index.intersection(fresh.index)
                a,b = old.loc[dates,"Close"], fresh.loc[dates,"Close"]
                delta = b.pct_change()-a.pct_change()
                row.update({"overlap_rows": len(dates), "old_last": str(old.index.max().date()),
                            "max_close_relative_revision": float((b/a-1).abs().max()),
                            "max_daily_return_revision": float(delta.abs().max()),
                            "daily_return_revisions_over_1bp": int((delta.abs()>.0001).sum())})
                for column in ("Open", "High", "Low", "Volume"):
                    previous, current = old.loc[dates, column], fresh.loc[dates, column]
                    valid = previous.ne(0)
                    row[f"max_{column.lower()}_relative_revision"] = float((current[valid]/previous[valid]-1).abs().max())
            rows.append(row)
    pd.DataFrame(rows).to_csv(out/"data_coverage_and_revisions.csv", index=False)


def native_prior_overlap(out):
    prior = ROOT/"research/trading-ledger-2026-09-05/core90_current_contract_2026_09_05/validated_2_1"
    sources = []
    with zipfile.ZipFile(prior/"source_bundle.zip") as bundle:
        for name in bundle.namelist():
            current = ROOT.parent/name
            if current.is_file():
                old_hash = hashlib.sha256(bundle.read(name)).hexdigest()
                new_hash = hashlib.sha256(current.read_bytes()).hexdigest()
                sources.append({"path": name, "old_sha256": old_hash, "new_sha256": new_hash, "same": old_hash == new_hash})
    dump(out/"native_prior_source_comparison.json", sources)
    path = out/"next_open/nav_Core90_Bull10.csv"
    if not path.exists():
        return
    old = pd.read_csv(prior/"daily_nav.csv", parse_dates=["valuation_date"]).set_index("valuation_date").net_nav
    fresh = pd.read_csv(path, index_col=0, parse_dates=True).nav
    dates = old.index.intersection(fresh.index)
    paired = pd.DataFrame({"old_nav": old.loc[dates], "fresh_nav": fresh.loc[dates]})
    paired.to_csv(out/"Bull_prior_review_overlap.csv")
    dump(out/"Bull_overlap_audit.json", {"start": str(dates[0].date()), "end": str(dates[-1].date()),
         "old_end_nav": float(old.loc[dates[-1]]), "fresh_end_nav": float(fresh.loc[dates[-1]]),
         "max_nav_relative_difference": float((paired.fresh_nav/paired.old_nav-1).abs().max()),
         "new_since_prior_return": float(fresh.iloc[-1]/fresh.loc[dates[-1]]-1),
         "matched_frozen_sources": sum(row["same"] for row in sources), "compared_sources": len(sources),
         "note": "Frozen implementation hashes compared separately from revised OHLCV inputs; use fresh-to-fresh extension returns."})


def nav_overlap(out):
    old = pd.read_csv(ROOT/"outputs/theme-alpha-lvt-recent-3m-2026-09-06/nav_full.csv", parse_dates=["valuation_date"])
    old = old[old.strategy.eq("Core80_LVT20_Def200_Cash") & old.cap.eq(.5)].set_index("valuation_date").nav
    fresh = pd.read_csv(out/"replay/theme/nav_C_Def200_LVT20.csv", index_col=0, parse_dates=True).nav
    dates = old.index.intersection(fresh.index)
    paired = pd.DataFrame({"old_nav": old.loc[dates], "fresh_nav": fresh.loc[dates]})
    paired["daily_return_difference"] = paired.fresh_nav.pct_change()-paired.old_nav.pct_change()
    paired.to_csv(out/"C_prior_review_overlap.csv")
    return {"start": str(dates[0].date()), "end": str(dates[-1].date()), "old_end_nav": float(paired.old_nav.iloc[-1]),
            "fresh_end_nav": float(paired.fresh_nav.iloc[-1]),
            "max_daily_return_difference": float(paired.daily_return_difference.abs().max()),
            "new_since_9_4_return": float(fresh.iloc[-1]/fresh.loc["2026-09-04"]-1),
            "note": "Use fresh-to-fresh returns; never splice old NAV into a repriced input history."}


def asset_diagnostics(snapshot, out):
    rows, closes = [], {}
    for symbol in (*CORE, "BTC-USD", "QQQ", "SPY", "GLD", "511010.SS"):
        frame = pd.read_parquet(snapshot/f"{symbol}.parquet")
        series = frame.Close
        rows.append({"symbol": symbol, "date": str(series.index[-1].date()), "close_adjusted": float(series.iloc[-1]),
                     "ma200": float(series.tail(200).mean()), "distance_to_ma200": float(series.iloc[-1]/series.tail(200).mean()-1),
                     "drawdown_from_history_peak": float(series.iloc[-1]/series.max()-1),
                     "return_since_2026_06_30": float(series.iloc[-1]/series.loc[:"2026-06-30"].iloc[-1]-1)})
        closes[symbol] = series
    pd.DataFrame(rows).to_csv(out/"asset_observations.csv", index=False)
    # BTC/US risk correlation: use US sessions so weekend crypto returns are aggregated.
    aligned = pd.DataFrame({s: closes[s].reindex(closes["QQQ"].index) for s in ("BTC-USD","QQQ","SPY","GLD")}).dropna()
    returns = aligned.pct_change(fill_method=None).dropna()
    correlations = []
    for period,start in (("recent_3m","2026-06-30"),("2026_ytd","2025-12-31"),("since_2020","2019-12-31")):
        selected = returns.loc[returns.index>pd.Timestamp(start)]
        for symbol in ("QQQ","SPY","GLD"):
            correlations.append({"period":period,"pair":"BTC-USD/"+symbol,"observations":len(selected),"return_correlation":float(selected['BTC-USD'].corr(selected[symbol]))})
    pd.DataFrame(correlations).to_csv(out/"btc_correlations.csv", index=False)


def extra_tables(out):
    for dest in (out/"replay/theme", out/"replay/btc", out/"next_open"):
        annual, monthly_stats, monthly_rows, rolling_rows = [], [], [], []
        for path in dest.glob("nav_*.csv"):
            label = path.stem[4:]
            nav = pd.read_csv(path, index_col=0, parse_dates=True).nav
            returns = nav.pct_change().fillna(0)
            for years in (3, 5):
                ends = nav.index[nav.index >= nav.index[0]+pd.DateOffset(years=years)]
                if not len(ends):
                    rolling_rows.append({"strategy": label, "years": years, "windows": 0, "status": "INSUFFICIENT_HISTORY"})
                    continue
                starts = ends-pd.DateOffset(years=years)
                positions = nav.index.searchsorted(starts, side="right")-1
                window_returns = nav.loc[ends].to_numpy()/nav.iloc[positions].to_numpy()-1
                worst = int(np.argmin(window_returns))
                elapsed = (ends[worst]-nav.index[positions[worst]]).days/365.25
                rolling_rows.append({"strategy": label, "years": years, "windows": len(ends), "status": "AVAILABLE",
                                     "worst_total_return": float(window_returns[worst]),
                                     "worst_annualized_return": float((1+window_returns[worst])**(1/elapsed)-1),
                                     "worst_start": str(nav.index[positions[worst]].date()), "worst_end": str(ends[worst].date())})
            for year,values in returns.groupby(returns.index.year):
                annual.append({"strategy":label,"year":year,"return":float((1+values).prod()-1),"partial_year":year in (nav.index[0].year,nav.index[-1].year)})
            monthly = returns.resample("ME").apply(lambda x:(1+x).prod()-1)
            monthly_rows.extend({"strategy": label, "month": str(day.date()), "return": float(value)} for day, value in monthly.items())
            winners,losers = monthly[monthly>0],monthly[monthly<0]
            monthly_stats.append({"strategy":label,"monthly_win_rate":float((monthly>0).mean()),"average_winning_month":float(winners.mean()),
                                  "average_losing_month":float(losers.mean()),"best_month":float(monthly.max()),"worst_month":float(monthly.min()),
                                  "monthly_profit_factor":float(winners.sum()/abs(losers.sum())) if len(losers) else None,
                                  "underwater_share":float((nav<nav.cummax()).mean())})
        pd.DataFrame(annual).to_csv(dest/"annual_returns.csv",index=False)
        pd.DataFrame(monthly_stats).to_csv(dest/"monthly_stats.csv",index=False)
        pd.DataFrame(rolling_rows).to_csv(dest/"rolling_3y_5y.csv",index=False)
        if dest.name == "next_open":
            pd.DataFrame(monthly_rows).to_csv(dest/"monthly_returns.csv",index=False)


def btc_fx_sensitivity(snapshot, out):
    config = get_strategy("btc_supertrend_satellite")
    market = load_market(config,snapshot,datetime(2026,10,2,16,tzinfo=ZoneInfo("Asia/Shanghai")),"2016-05-01")
    targets,_ = btc_targets(config,market)
    fx = pd.read_parquet(snapshot/"CNY=X.parquet").Close
    # Previous available FX session avoids introducing a later same-day FX close.
    fx = fx.shift(1).reindex(market.sessions.union(fx.index)).ffill().reindex(market.sessions)
    if fx.isna().any():
        raise ValueError("Missing FX history")
    from dataclasses import replace
    converted = market.close.copy()
    converted["BTC-USD"] *= fx
    converted_market = replace(market,close=converted)
    nav,_,audit = replay(config,converted_market,targets["BTC_7.5"])
    nav.to_csv(out/"replay/btc/nav_BTC_7.5_fx_diagnostic.csv")
    dump(out/"btc_fx_diagnostic.json", {"status":"SUPPLEMENTAL_SENSITIVITY_NOT_FROZEN_CONTRACT",
         "assumption":"Frozen USD BTC signals; CNY valuation uses previous available FX close; no investable carrier or FX fees modeled",
         "full":summarize(nav,nav.index[0],nav.index[-1]), "recent_3m":summarize(nav,"2026-06-30",nav.index[-1]), "audit":audit})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    args=parser.parse_args()
    out=args.root
    dump(out/"legacy_btc_execution_finding.json",legacy_timing_evidence())
    source_overlap(out/"market_data",out)
    native_prior_overlap(out)
    dump(out/"C_overlap_audit.json",nav_overlap(out))
    asset_diagnostics(out/"market_data",out)
    extra_tables(out)
    if (out/"market_data/CNY=X.parquet").exists():
        btc_fx_sensitivity(out/"market_data",out)


if __name__ == "__main__":
    main()
