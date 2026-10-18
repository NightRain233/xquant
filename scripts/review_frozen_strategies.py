"""Review frozen strategy implementations on an isolated market snapshot.

Uses trading's signal functions and fractional next-close execution solver.
New ablations are explicitly labelled, never treated as frozen candidates.
Run with trading/backend/.venv/bin/python; no production account is touched.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT.parent / "trading/backend"
sys.path.insert(0, str(BACKEND))
from portfolio_strategies.btc_satellite import calculate_btc_satellite
from portfolio_strategies.indicators import InsufficientDataError, inverse_volatility_weights
from portfolio_strategies.market_data import build_portfolio_market_data
from portfolio_strategies.paper_engine import PortfolioPaperEngine
from portfolio_strategies.registry import get_strategy
from portfolio_strategies.schedules import bimonthly_signal_dates, every_n_session_dates
from portfolio_strategies.theme_alpha import calculate_theme_alpha, combine_sleeve_weights

CORE = ("510300.SS", "513100.SS", "518880.SS")


def builtin(value):
    if is_dataclass(value):
        return {f.name: builtin(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): builtin(v) for k,v in value.items()}
    if isinstance(value, (tuple, list)):
        return [builtin(x) for x in value]
    return value


def dump(path, value):
    path.write_text(json.dumps(builtin(value), ensure_ascii=False, indent=2, default=str) + "\n")


def load_market(config, source, as_of, start):
    frames = {s: pd.read_parquet(source / f"{s}.parquet").loc[start:] for s in config.symbols}
    market = build_portfolio_market_data(config, frames, as_of)
    if market.blocked:
        raise ValueError(json.dumps(builtin(market.diagnostics), default=str))
    # The production loader checks recent gaps; also audit the full common calendar.
    from portfolio_strategies.schedules import xshg_sessions
    expected = xshg_sessions(market.sessions[0], market.sessions[-1])
    missing = expected.difference(market.sessions)
    # Issuer notice: 513100 suspended for a share split on 2022-01-13.
    # https://static.cninfo.com.cn/finalpage/2022-01-04/1212087910.PDF
    # Preserve the frozen common-session model; do not manufacture a tradable bar.
    explained = {pd.Timestamp("2022-01-13")} if "513100.SS" in frames else set()
    unexplained = [day for day in missing if day not in explained]
    if unexplained:
        raise ValueError(f"Historical aligned session gaps: {unexplained[:8]}")
    if market.close.isna().any().any() or (market.close <= 0).any().any():
        raise ValueError("Invalid aligned prices")
    return market


def theme_targets(config, market):
    labels = ("C_Def200_LVT20", "C_Base_LVT20", "RP_C_schedule", "RP90_Cash10_C_schedule", "LVT100", "RP_Def200_ablation")
    targets = {label: {} for label in labels}
    observations = []
    returns = market.close.pct_change(fill_method=None)
    for day in sorted(bimonthly_signal_dates(market.sessions, signal_days=config.params["signal_days"])):
        try:
            calc = calculate_theme_alpha(config, market, day.date())
        except InsufficientDataError:
            if targets[labels[0]]:
                raise
            continue
        core = inverse_volatility_weights(returns.loc[:day], CORE, window=20)
        defended = {x.symbol: x.weight for x in calc.sleeve_weights["core"]}
        lvt = {x.symbol: x.weight for x in calc.sleeve_weights["lvt"]}
        targets[labels[0]][day] = {x.symbol: x.weight for x in calc.target_weights}
        targets[labels[1]][day] = combine_sleeve_weights(core, lvt, symbols=config.symbols, core_allocation=.8, lvt_allocation=.2)
        targets[labels[2]][day] = {**core, "CASH": 0.0}
        targets[labels[3]][day] = {**{s: .9*w for s, w in core.items()}, "CASH": .1}
        targets[labels[4]][day] = lvt
        targets[labels[5]][day] = defended
        observations.append({"signal_date": str(day.date()), **calc.observation.values})
    return targets, observations


def btc_targets(config, market):
    targets = {"BTC_0": {}, "BTC_5": {}, "BTC_7.5": {}, "BTC_10": {}, "RP92.5_Cash7.5": {}}
    observations = []
    for day in sorted(every_n_session_dates(config.params["schedule_reference_date"], market.sessions, every=10)):
        try:
            calc = calculate_btc_satellite(config, market, day.date())
        except InsufficientDataError:
            if targets["BTC_0"]:
                raise
            continue
        official = {x.symbol: x.weight for x in calc.target_weights}
        core = {s: official[s] / .925 for s in CORE}
        on = bool(calc.observation.values["formal_supertrend_on"])
        for cap in (0., .05, .075, .10):
            label = f"BTC_{cap*100:g}"
            targets[label][day] = {**{s: (1-cap)*w for s,w in core.items()}, "BTC-USD": cap if on else 0., "CASH": 0. if on else cap}
        targets["RP92.5_Cash7.5"][day] = {**{s: .925*w for s,w in core.items()}, "BTC-USD": 0., "CASH": .075}
        observations.append({"signal_date": str(day.date()), **calc.observation.values})
    return targets, observations


def replay(config, market, targets, *, extra_cost_bps=0.):
    """Chronological next-close replay with independent cash-flow checks."""
    if not targets:
        raise ValueError("No valid formal signals")
    if extra_cost_bps:
        config = replace(config, costs=replace(config.costs, base_bps=config.costs.base_bps + extra_cost_bps))
    engine = PortfolioPaperEngine.__new__(PortfolioPaperEngine)
    execution = {}
    for day, target in targets.items():
        if abs(sum(target.values()) - 1.) > 1e-9 or min(target.values()) < 0:
            raise ValueError("Invalid target")
        position = market.sessions.get_loc(day) + 1
        if position < len(market.sessions):
            execution[market.sessions[position]] = (day, target)
    first = market.sessions.get_loc(min(targets)) - 1
    if first < 0:
        raise ValueError("No pre-signal activation day")
    cash, quantities = 100_000., {s: 0. for s in config.symbols}
    rows, events = [], []
    max_cash_error = max_nav_error = 0.
    for day in market.sessions[first:]:
        prices = market.close.loc[day].to_dict()
        values = {s: quantities[s] * prices[s] for s in config.symbols}
        gross = cash + sum(values.values())
        if day in execution:
            signal, desired = execution[day]
            desired = {s: float(desired.get(s, 0.)) for s in (*config.symbols, "CASH")}
            current = {s: v/gross for s,v in values.items()}
            current["CASH"] = cash/gross
            execute, turnover = engine._should_execute(config, current, desired)
            executable = engine._executable_weights(config, current, desired)
            cost = notional = 0.
            if execute:
                net, new_values, fees = engine._solve_execution(config, values, gross, executable)
                cost = sum(f+s for _,f,s in fees.values())
                notional = sum(n for n,_,_ in fees.values())
                new_quantities = {s: new_values[s]/prices[s] for s in config.symbols}
                cash_flow = sum((new_quantities[s]-quantities[s])*prices[s] for s in config.symbols)
                reconstructed_cash = cash-cash_flow-cost
                cash = executable["CASH"]*net
                quantities = new_quantities
                max_cash_error = max(max_cash_error, abs(cash-reconstructed_cash))
                max_nav_error = max(max_nav_error, abs(net-(gross-cost)))
            events.append({"signal_date": str(signal.date()), "execution_date": str(day.date()), "executed": execute,
                           "turnover": turnover, "notional": notional, "cost": cost, "gross_nav": gross,
                           "target": json.dumps(desired), "executable": json.dumps(executable)})
        values = {s: quantities[s]*prices[s] for s in config.symbols}
        nav = cash + sum(values.values())
        if cash < -1e-6 or nav <= 0 or not np.isfinite(nav):
            raise ValueError("Invalid cash/NAV")
        rows.append({"date": day, "nav": nav, "cash_weight": cash/nav,
                     **{f"weight_{s}": v/nav for s,v in values.items()}})
    if max_cash_error > 1e-5 or max_nav_error > 1e-5:
        raise AssertionError(f"Execution conservation failed: {max_cash_error}, {max_nav_error}")
    return pd.DataFrame(rows).set_index("date"), pd.DataFrame(events), {"max_cash_error": max_cash_error, "max_nav_error": max_nav_error, "timing": "next_complete_XSHG_close"}


def summarize(nav, start, end):
    full = nav.loc[:end]
    # Include the close at/before the boundary so the first day's P&L is retained.
    anchor = full.index[full.index <= pd.Timestamp(start)]
    anchor = anchor[-1] if len(anchor) else full.index[0]
    selected = full.loc[anchor:]
    if len(selected) < 2:
        return None
    s = selected.nav
    returns = s.pct_change().dropna()
    years = (s.index[-1]-s.index[0]).days/365.25
    drawdown = s/s.cummax()-1
    underwater = drawdown < -1e-12
    longest = current = 0
    for value in underwater:
        current = current+1 if value else 0
        longest = max(longest, current)
    result = {"start": str(s.index[0].date()), "end": str(s.index[-1].date()), "observations": len(returns),
              "return": float(s.iloc[-1]/s.iloc[0]-1), "max_drawdown": float(drawdown.min()),
              "current_drawdown_window": float(drawdown.iloc[-1]),
              "current_drawdown_since_activation": float((full.nav/full.nav.cummax()-1).iloc[-1]),
              "annualized_volatility": float(returns.std(ddof=1)*np.sqrt(252)),
              "longest_underwater_sessions": longest, "mean_cash_weight": float(selected.cash_weight.mean()),
              "max_asset_weight": float(selected.filter(like="weight_").max().max())}
    # Do not turn a short recent window into a seductive annualized headline.
    result["cagr"] = float((s.iloc[-1]/s.iloc[0])**(1/years)-1) if years >= 1 else None
    result["sharpe_zero_rf"] = float(returns.mean()/returns.std(ddof=1)*np.sqrt(252)) if years >= 1 and returns.std(ddof=1)>0 else None
    result["calmar"] = result["cagr"] / abs(result["max_drawdown"]) if result["cagr"] is not None and result["max_drawdown"] < 0 else None
    return result


def run_family(family, source, out, as_of):
    config = get_strategy("theme_alpha" if family == "theme" else "btc_supertrend_satellite")
    market = load_market(config, source, as_of, "2021-07-01" if family == "theme" else "2016-05-01")
    targets, observations = theme_targets(config, market) if family == "theme" else btc_targets(config, market)
    dest = out/family
    dest.mkdir(exist_ok=False)
    dump(dest/"config.json", config)
    dump(dest/"signals.json", observations)
    end = market.sessions[-1]
    windows = {"full_common": min(min(t) for t in targets.values()) - pd.Timedelta(days=1),
               "2026_ytd": pd.Timestamp("2025-12-31"), "since_2026_06_26": pd.Timestamp("2026-06-26"),
               "since_prior_review": pd.Timestamp("2026-09-04" if family == "theme" else "2026-08-10"),
               "recent_3m": end-pd.DateOffset(months=3)}
    summaries, audits, latest, monthly = [], [], [], []
    all_nav = {}
    for label, target in targets.items():
        nav, events, audit = replay(config, market, target)
        nav.to_csv(dest/f"nav_{label}.csv")
        events.to_csv(dest/f"events_{label}.csv", index=False)
        all_nav[label] = nav
        audits.append({"strategy": label, **audit})
        latest.append({"strategy": label, "signal_date": str(max(target).date()), "target": target[max(target)],
                       "valuation_date": str(end.date()), "actual_weights": nav.iloc[-1].filter(like="weight_").to_dict(), "cash_weight": float(nav.iloc[-1].cash_weight)})
        for name, start in windows.items():
            metrics = summarize(nav, start, end)
            if metrics:
                period_events = events[(pd.to_datetime(events.execution_date)>pd.Timestamp(metrics["start"])) & (pd.to_datetime(events.execution_date)<=end)]
                metrics.update({"strategy": label, "period": name, "execution_count": int(period_events.executed.sum()),
                                "cost_nav_ratio_sum": float((period_events.cost/period_events.gross_nav).sum())})
                summaries.append(metrics)
        monthly_returns = nav.nav.pct_change().fillna(0).resample("ME").apply(lambda x: (1+x).prod()-1)
        monthly.extend({"strategy": label, "month": str(day.date()), "return": float(value)} for day,value in monthly_returns.items())
        print(f"Replayed {family}/{label} through {end.date()}", flush=True)
    # Actual extra-cost replays, preserving decisions but re-evaluating turnover/holdings.
    official = "C_Def200_LVT20" if family == "theme" else "BTC_7.5"
    sensitivity = []
    for extra in (10., 20.):
        nav, _, audit = replay(config, market, targets[official], extra_cost_bps=extra)
        sensitivity.append({"strategy": official, "extra_cost_bps": extra, **summarize(nav, windows["full_common"], end), **audit})
    pd.DataFrame(sensitivity).to_csv(dest/"cost_sensitivity.csv", index=False)
    pd.DataFrame(summaries).to_csv(dest/"summary.csv", index=False)
    pd.DataFrame(monthly).to_csv(dest/"monthly_returns.csv", index=False)
    dump(dest/"latest.json", latest)
    dump(dest/"execution_audit.json", audits)
    return {"family": family, "end": str(end.date()), "strategies": list(targets)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--families", nargs="+", choices=("theme", "btc"), default=["theme", "btc"])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    now = datetime.fromisoformat(args.as_of).replace(hour=16, tzinfo=ZoneInfo("Asia/Shanghai"))
    results = []
    for family in args.families:
        try:
            results.append(run_family(family, args.snapshot, args.output, now))
        except Exception as exc:
            results.append({"family": family, "status": "BLOCKED", "error": type(exc).__name__, "message": str(exc)})
            print(results[-1], flush=True)
    sources = [Path(__file__), *(BACKEND/"portfolio_strategies").glob("*.py")]
    dump(args.output/"source_hashes.json", {str(p.relative_to(ROOT.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    dump(args.output/"run_status.json", results)
    return int(any(x.get("status") == "BLOCKED" for x in results))


if __name__ == "__main__":
    raise SystemExit(main())
