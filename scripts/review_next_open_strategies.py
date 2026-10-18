"""Replay the frozen next-open core and Bull10 contracts on a new snapshot."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent/"trading/backend"))
from portfolio_strategies.core_bull_research import run_current_contract
from portfolio_strategies.frozen_xquant import frozen_universe
from portfolio_strategies.registry import get_strategy
from review_frozen_strategies import CORE, dump, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--end", default="2026-09-30")
    parser.add_argument("--bull-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/"cache").mkdir(exist_ok=True)
    audit_path = ROOT/"research/trading-ledger-2026-09-05/core90_current_contract_2026_09_05/recompute.py"
    spec = importlib.util.spec_from_file_location("native_audit", audit_path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    core = get_strategy("risk_parity_core_next_open")
    filtered = replace(core, strategy_id="risk_parity_core_supertrend_filter", params={**core.params, "core_supertrend_atr_window": 10, "core_supertrend_multiplier": 3.})
    variants = [("RP_native", core, False, False), ("RP90_Cash10_native", get_strategy("core90_ma200_bull10"), False, False),
                ("RP_ST_filter_native", filtered, False, True)]
    if args.bull_only:
        variants = [("Core90_Bull10", get_strategy("core90_ma200_bull10"), True, False)]
    summaries, audits = [], []
    for label, config, bull, st in variants:
        symbols = frozen_universe().symbols if bull else CORE
        missing = [s for s in symbols if not (args.snapshot/f"{s}.parquet").exists()]
        if missing:
            dump(args.output/f"blocked_{label}.json", {"reason": "Missing frozen universe members; do not shrink the pool", "symbols": missing})
            continue
        frames = {s: pd.read_parquet(args.snapshot/f"{s}.parquet") for s in symbols}
        if min(frames[s].index.max() for s in CORE) < pd.Timestamp(args.end):
            raise ValueError("Core snapshot is stale")
        db = args.output/"cache"/f"{label}.sqlite"
        print(f"Starting {label}", flush=True)
        run_current_contract(config, frames, start=date(2015,1,1), end=date.fromisoformat(args.end), db_path=db,
                             include_bull=bull, core_supertrend_filter=st)
        with sqlite3.connect(db) as conn:
            nav = pd.read_sql_query("SELECT valuation_date,net_nav,cash FROM portfolio_nav_v2 WHERE authoritative=1 ORDER BY valuation_date", conn)
            quantities = audit.audit_quantities(conn)
            cash, invalid = audit.audit_cash_and_timing(conn, config.initial_nav)
            fills = pd.read_sql_query("SELECT e.*,o.symbol,o.sleeve FROM paper_executions e JOIN paper_orders o ON o.id=e.order_id", conn)
        nav = nav.rename(columns={"valuation_date": "date", "net_nav": "nav"})
        nav["date"] = pd.to_datetime(nav.date)
        nav = nav.set_index("date")
        nav["cash_weight"] = nav.cash/nav.nav
        nav["weight_assets_total"] = 1-nav.cash_weight
        nav.to_csv(args.output/f"nav_{label}.csv")
        fills.to_csv(args.output/f"fills_{label}.csv", index=False)
        entry = {"strategy": label, "quantity_mismatches": len(quantities), "max_cash_error": float(cash.difference.abs().max()), "invalid_timing_fills": invalid}
        entry["passed"] = not entry["quantity_mismatches"] and entry["max_cash_error"] < 1e-5 and not invalid
        audits.append(entry)
        if not entry["passed"]:
            raise ValueError(f"Audit failed: {entry}")
        for period, start in {"full_common": "2015-01-01", "since_prior_review": "2026-07-10", "2026_ytd": "2025-12-31", "recent_3m": "2026-06-30", "september": "2026-08-31"}.items():
            metrics = summarize(nav, start, args.end)
            if metrics:
                selected = nav.loc[pd.Timestamp(metrics["start"]):pd.Timestamp(args.end)].nav
                years = (selected.index[-1]-selected.index[0]).days/365.25
                returns = selected.pct_change().dropna()
                annualization = len(returns)/years
                metrics["annualized_volatility"] = float(returns.std(ddof=1)*annualization**.5)
                metrics["sharpe_zero_rf"] = float(returns.mean()/returns.std(ddof=1)*annualization**.5) if years>=1 else None
                # Per-asset concentration is not available in this NAV-only summary.
                metrics["max_asset_weight"] = None
                summaries.append({"strategy": label, "period": period, **metrics})
        dump(args.output/f"config_{label}.json", config)
        print(f"Completed {label}", flush=True)
    suffix = "bull" if args.bull_only else "core"
    pd.DataFrame(summaries).to_csv(args.output/f"summary_{suffix}.csv", index=False)
    dump(args.output/f"audit_{suffix}.json", audits)


if __name__ == "__main__":
    main()
