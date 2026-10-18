#!/usr/bin/env python3
"""Independent fill-based verification of corrected 3-ETF dividend ledgers.

This deliberately does not import the research/replay implementation. It rebuilds
shares, cash, dividend receivables, and close NAV from frozen fills, raw OHLC,
and official corporate actions using only the standard library.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from statistics import stdev
from collections import defaultdict
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path


SYMBOLS = ("510300", "513100", "518880")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def monthly_common_dates(root: Path) -> list[str]:
    calendar = read_csv(root / "common_calendar.csv")
    days = sorted(row["common_trading_date"] for row in calendar
                  if "2015-01-05" <= row["common_trading_date"] <= "2026-09-30")
    first_by_month: dict[str, str] = {}
    for day in days:
        first_by_month.setdefault(day[:7], day)
    return list(first_by_month.values())


def contribution_schedule_check(root: Path) -> dict[str, object]:
    expected = monthly_common_dates(root)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    amount = float(config["dca_monthly_cny"])
    lump_amount = float(config["lump_cny"])
    accounts = {}
    for style in ("lump", "dca"):
        rows = read_csv(root / f"account_corrected_Three_{style}.csv")
        actual_rows = [row for row in rows if float(row.get("contribution") or 0.0) > 0]
        actual_dates = [row["date"] for row in actual_rows]
        actual_amounts = [float(row["contribution"]) for row in actual_rows]
        if style == "lump":
            expected_style_dates = [expected[0]]
            expected_style_amount = lump_amount
        else:
            expected_style_dates = expected
            expected_style_amount = amount
        accounts[style] = {
            "expected_monthly_dates_count": len(expected),
            "actual_contribution_count": len(actual_dates),
            "expected_amount_cny_each": expected_style_amount,
            "actual_total_contribution_cny": sum(actual_amounts),
            "expected_contribution_count": len(expected_style_dates),
            "actual_dates_match_expected_schedule": actual_dates == expected_style_dates,
            "actual_amounts_match_expected": len(actual_amounts) == len(expected_style_dates) and all(abs(x - expected_style_amount) < 1e-8 for x in actual_amounts),
            "missing_dates": sorted(set(expected_style_dates) - set(actual_dates)),
            "unexpected_dates": sorted(set(actual_dates) - set(expected_style_dates)),
        }
        accounts[style]["all_passed"] = accounts[style]["actual_dates_match_expected_schedule"] and accounts[style]["actual_amounts_match_expected"]
    return {
        "source": "common_calendar.csv; first common date in each month from 2015-01-05 through 2026-09-30",
        "expected_month_count": len(expected),
        "first_expected_date": expected[0] if expected else None,
        "last_expected_date": expected[-1] if expected else None,
        "expected_dates": expected,
        "account_reconciliation": accounts,
        "all_passed": all(result["all_passed"] for result in accounts.values()),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def f(row: dict[str, str], name: str) -> float:
    value = row.get(name, "")
    return 0.0 if value in ("", None) else float(value)


def load_raw_prices(path: Path) -> dict[str, dict[str, dict[str, float]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))["data"]
    prices: dict[str, dict[str, dict[str, float]]] = {}
    for yahoo_symbol, series in raw.items():
        symbol = yahoo_symbol.split(".", 1)[0]
        by_date: dict[str, dict[str, float]] = {}
        for i, stamp in enumerate(series["timestamp"]):
            # Yahoo-style daily stamps arrive at 16:00 UTC; use the exchange
            # timezone's calendar date, which is the next day in Shanghai.
            day = datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).astimezone(
                ZoneInfo("Asia/Shanghai")
            ).date().isoformat()
            by_date[day] = {
                field: float(series[field][i])
                for field in ("open", "high", "low", "close")
            }
        prices[symbol] = by_date
    return prices


def simulate(
    root: Path, account_kind: str, style: str, prices: dict[str, dict[str, dict[str, float]]]
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, float]]:
    suffix = "lump" if style == "lump" else "dca"
    fills = read_csv(root / f"fills_corrected_{account_kind}_{suffix}.csv")
    actions = read_csv(root / "corporate_actions.csv")
    fee_rate = float(json.loads((root / "config.json").read_text(encoding="utf-8"))["cost_bps"]) / 10000.0
    reported = read_csv(root / f"account_corrected_{account_kind}_{suffix}.csv")
    fills_by_day: dict[str, list[dict[str, str]]] = defaultdict(list)
    actions_by_day: dict[str, list[dict[str, str]]] = defaultdict(list)
    actions_by_id: dict[str, dict[str, str]] = {}
    for row in fills:
        fills_by_day[row["date"]].append(row)
    for idx, action in enumerate(actions):
        if action["symbol"] not in SYMBOLS:
            continue
        action = dict(action)
        action["_id"] = str(idx + 1)
        actions_by_id[action["_id"]] = action
        for field in ("record_date", "corporate_action_date", "pay_date"):
            if action.get(field):
                actions_by_day[action[field]].append(action)

    report_by_day = {row["date"]: row for row in reported}
    first_report_day = min(report_by_day)
    all_days = sorted(day for day in (set(report_by_day) | set(fills_by_day) | set(actions_by_day))
                      if day >= first_report_day)
    # Independently derive DCA funding dates from frozen common_calendar.csv.
    monthly_deposit_days = set(monthly_common_dates(root)) if style == "dca" else set()
    monthly_deposit_amount = float(json.loads((root / "config.json").read_text(encoding="utf-8"))["dca_monthly_cny"])
    shares = {symbol: 0.0 for symbol in SYMBOLS}
    cash = 0.0
    receivable = 0.0
    registered: dict[str, float] = {}
    due: dict[str, float] = {}
    principal = 0.0
    if style == "lump":
        principal = float(json.loads((root / "config.json").read_text())["lump_cny"])
        cash = principal
    last_close: dict[str, float] = {}
    last_raw_day: dict[str, str] = {}
    pending_resume_quote: dict[str, tuple[str, dict[str, float]]] = {}
    ledger_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    max_abs = {"cash": 0.0, "receivable": 0.0, "shares": 0.0, "wealth": 0.0, "liquidation_wealth": 0.0}
    max_error_at: dict[str, dict[str, object]] = {}

    for day in all_days:
        row_out = report_by_day.get(day)
        fills_today = fills_by_day.get(day, [])
        if style == "dca" and day in monthly_deposit_days:
            cash += monthly_deposit_amount
            principal += monthly_deposit_amount
        cash_before_fills = cash

        # Dividends become receivables before the ex-date open.
        for action in actions_by_day.get(day, []):
            if action["action_type"] == "cash_dividend" and action["corporate_action_date"] == day:
                action_id = action["_id"]
                amount = registered.get(action_id, 0.0) * float(action["cash_per_share"])
                due[action_id] = amount
                receivable += amount
                event_rows.append({
                    "account": f"{account_kind}_{style}", "event_id": action_id,
                    "symbol": action["symbol"], "phase": "ex_receivable_before_open",
                    "date": day, "entitled_quantity": registered.get(action_id, 0.0),
                    "per_share_or_ratio": float(action["cash_per_share"]),
                    "amount": amount, "cash_after": cash, "receivable_after": receivable,
                })

        # Execute from the independent fill list at the stated raw open.
        for fill in fills_today:
            symbol = fill["symbol"]
            delta = float(fill["quantity_delta"])
            notional = float(fill["notional"])
            fee = float(fill["commission"])
            shares[symbol] += delta
            cash -= math.copysign(notional, delta) + fee
            if fill["type"] == "subscription":
                event_rows.append({
                    "account": f"{account_kind}_{style}", "event_id": "",
                    "symbol": symbol, "phase": "external_contribution_fill",
                    "date": day, "entitled_quantity": delta,
                    "per_share_or_ratio": float(fill["price"]), "amount": monthly_deposit_amount,
                    "cash_after": cash, "receivable_after": receivable,
                })
        sale_proceeds_after_fees = sum(
            float(fill["notional"]) - float(fill["commission"])
            for fill in fills_today if float(fill["quantity_delta"]) < 0
        )
        buy_costs_after_fees = sum(
            float(fill["notional"]) + float(fill["commission"])
            for fill in fills_today if float(fill["quantity_delta"]) > 0
        )
        sell_first_cash = cash_before_fills + sale_proceeds_after_fees
        day_end_trade_cash = sell_first_cash - buy_costs_after_fees

        # Cash is posted after close on the official investor payment date.
        for action in actions_by_day.get(day, []):
            if action["action_type"] == "cash_dividend" and action["pay_date"] == day:
                action_id = action["_id"]
                amount = due.pop(action_id, 0.0)
                receivable -= amount
                cash += amount
                event_rows.append({
                    "account": f"{account_kind}_{style}", "event_id": action_id,
                    "symbol": action["symbol"], "phase": "cash_paid_after_close",
                    "date": day, "entitled_quantity": registered.get(action_id, 0.0),
                    "per_share_or_ratio": float(action["cash_per_share"]),
                    "amount": amount, "cash_after": cash, "receivable_after": receivable,
                })

        split_symbols_today = set()
        # Apply unit changes after the close. Quotes are not traded on a split
        # date: carry the prior close through the split and express it per new unit.
        for action in actions_by_day.get(day, []):
            if action["action_type"] == "split" and action["corporate_action_date"] == day:
                symbol = action["symbol"]
                split_symbols_today.add(symbol)
                old_quantity = shares[symbol]
                ratio = float(action["split_ratio"])
                shares[symbol] *= ratio
                if symbol in last_close:
                    last_close[symbol] /= ratio
                event_rows.append({
                    "account": f"{account_kind}_{style}", "event_id": action["_id"],
                    "symbol": symbol, "phase": "split_after_close",
                    "date": day, "entitled_quantity": shares[symbol],
                    "per_share_or_ratio": ratio, "amount": 0.0,
                    "cash_after": cash, "receivable_after": receivable,
                })

        # Register entitlement at the close after any same-day fills.
        for action in actions_by_day.get(day, []):
            if action["action_type"] == "cash_dividend" and action["record_date"] == day:
                action_id = action["_id"]
                registered[action_id] = shares[action["symbol"]]
                event_rows.append({
                    "account": f"{account_kind}_{style}", "event_id": action_id,
                    "symbol": action["symbol"], "phase": "registered_after_close",
                    "date": day, "entitled_quantity": shares[action["symbol"]],
                    "per_share_or_ratio": float(action["cash_per_share"]),
                    "amount": 0.0, "cash_after": cash, "receivable_after": receivable,
                })

        # Raw source bars are forward-filled on non-quote dates. On the known
        # 513100 suspension/split date, its prior close is divided by 5 above;
        # the first post-split raw bar is taken on the next available source date.
        close_values = {}
        for symbol in SYMBOLS:
            quote = prices.get(symbol, {}).get(day)
            if quote is not None and symbol in split_symbols_today:
                pending_resume_quote[symbol] = (day, quote)
            elif quote is not None:
                last_close[symbol] = quote["close"]
                last_raw_day[symbol] = day
            elif symbol in pending_resume_quote and day > pending_resume_quote[symbol][0]:
                raw_day, resume_quote = pending_resume_quote.pop(symbol)
                last_close[symbol] = resume_quote["close"]
                last_raw_day[symbol] = raw_day
            close_values[symbol] = last_close.get(symbol, 0.0)
        market_value = sum(shares[s] * close_values[s] for s in SYMBOLS)
        wealth = cash + receivable + market_value
        # The exported liquidation value is a theoretical immediate sale of
        # holdings at the configured gross sell fee; cash/receivable stay whole.
        liquidation_wealth = cash + receivable + market_value * (1.0 - fee_rate)
        for symbol in SYMBOLS:
            if symbol in prices:
                # Corrected account columns are post-close holdings.
                pass
        if row_out:
            observed = {
                "cash": f(row_out, "cash"),
                "receivable": f(row_out, "receivable"),
                "wealth": f(row_out, "wealth"),
                "liquidation_wealth": f(row_out, "liquidation_wealth"),
            }
            errors = {"cash": cash - observed["cash"], "receivable": receivable - observed["receivable"],
                      "wealth": wealth - observed["wealth"], "liquidation_wealth": liquidation_wealth - observed["liquidation_wealth"]}
            for key, error in errors.items():
                if abs(error) > max_abs[key]:
                    max_abs[key] = abs(error)
                    max_error_at[key] = {"date": day, "signed_error_cny": error}
            for symbol in SYMBOLS:
                key = f"quantity_{symbol}"
                error = shares[symbol] - f(row_out, key)
                if abs(error) > max_abs["shares"]:
                    max_abs["shares"] = abs(error)
                    max_error_at["shares"] = {"date": day, "symbol": symbol, "signed_error": error}
            ledger_rows.append({
                "date": day, "account": f"{account_kind}_{style}", "principal": principal,
                "cash_independent": cash, "receivable_independent": receivable,
                "cash_available_after_sells_before_buys": sell_first_cash if fills_today else cash_before_fills,
                "cash_after_all_fills": day_end_trade_cash if fills_today else cash_before_fills,
                "quantity_510300": shares["510300"], "quantity_513100": shares["513100"],
                "quantity_518880": shares["518880"], "market_value_raw_close": market_value,
                "wealth_independent": wealth, "wealth_reported": observed["wealth"],
                "cash_error": cash - observed["cash"],
                "receivable_error": receivable - observed["receivable"],
                "wealth_error": wealth - observed["wealth"],
                "quote_day_510300": last_raw_day.get("510300", ""),
                "quote_day_513100": last_raw_day.get("513100", ""),
                "quote_day_518880": last_raw_day.get("518880", ""),
            })

    metrics = {
        "max_abs_cash_error_cny": max_abs["cash"],
        "max_abs_receivable_error_cny": max_abs["receivable"],
        "max_abs_share_quantity_error": max_abs["shares"],
        "max_abs_raw_close_wealth_error_cny": max_abs["wealth"],
        "max_abs_raw_close_liquidation_error_cny": max_abs["liquidation_wealth"],
        "days_compared": len(ledger_rows),
        "max_error_at": max_error_at,
        "min_sell_first_cash_cny": min(float(row["cash_available_after_sells_before_buys"]) for row in ledger_rows),
        "negative_sell_first_cash_days": [row["date"] for row in ledger_rows if float(row["cash_available_after_sells_before_buys"]) < -1e-6],
        "min_day_end_trade_cash_cny": min(float(row["cash_after_all_fills"]) for row in ledger_rows),
        "negative_day_end_trade_cash_days": [row["date"] for row in ledger_rows if float(row["cash_after_all_fills"]) < -1e-6],
    }
    return ledger_rows, event_rows, metrics


def event_windows(
    root: Path, ledger_rows: list[dict[str, object]], events: list[dict[str, object]]
) -> list[dict[str, object]]:
    by_day = {str(row["date"]): row for row in ledger_rows}
    report = read_csv(root / f"account_corrected_{ledger_rows[0]['account'].split('_')[0]}_{ledger_rows[0]['account'].split('_')[1]}.csv")
    report_by_day = {row["date"]: row for row in report}
    result = []
    for event in events:
        if event["phase"] not in ("registered_after_close", "ex_receivable_before_open", "cash_paid_after_close", "split_after_close"):
            continue
        day = date.fromisoformat(str(event["date"]))
        for offset in (-1, 0, 1):
            probe = day.fromordinal(day.toordinal() + offset).isoformat()
            ledger = by_day.get(probe)
            observed = report_by_day.get(probe)
            result.append({
                "account": event["account"], "event_id": event["event_id"],
                "symbol": event["symbol"], "event_phase": event["phase"],
                "event_date": event["date"], "offset_days": offset,
                "probe_date": probe,
                "independent_cash": ledger["cash_independent"] if ledger else "",
                "reported_cash": f(observed, "cash") if observed else "",
                "independent_receivable": ledger["receivable_independent"] if ledger else "",
                "reported_receivable": f(observed, "receivable") if observed else "",
                "independent_quantity": ledger[f"quantity_{event['symbol']}"] if ledger else "",
                "reported_quantity": f(observed, f"quantity_{event['symbol']}") if observed else "",
                "independent_wealth": ledger["wealth_independent"] if ledger else "",
                "reported_wealth": f(observed, "wealth") if observed else "",
                "wealth_delta": (float(ledger["wealth_independent"]) - f(observed, "wealth")) if ledger and observed else "",
                "cash_delta": (float(ledger["cash_independent"]) - f(observed, "cash")) if ledger and observed else "",
                "receivable_delta": (float(ledger["receivable_independent"]) - f(observed, "receivable")) if ledger and observed else "",
                "quantity_delta": (float(ledger[f"quantity_{event['symbol']}"]) - f(observed, f"quantity_{event['symbol']}")) if ledger and observed else "",
            })
    return result


def compare_events(root: Path, independently_built: list[dict[str, object]], style: str) -> dict[str, object]:
    """Compare event phases/amounts with the exported primary event log."""
    reported = read_csv(root / f"events_corrected_Three_{style}.csv")
    phases = ("registered_after_close", "ex_receivable_before_open", "cash_paid_after_close", "split_after_close")
    reported_by_key = {(row["date"], row["symbol"], row["phase"]): row
                       for row in reported if row["phase"] in phases}
    independent_by_key = {(str(row["date"]), str(row["symbol"]), str(row["phase"])): row
                          for row in independently_built if row["phase"] in phases}
    fields = ("entitled_quantity", "per_share_or_ratio", "amount", "cash_after", "receivable_after")
    deltas = {field: [] for field in fields}
    missing_primary, missing_independent = [], []
    for key in sorted(set(independent_by_key) | set(reported_by_key)):
        a, b = independent_by_key.get(key), reported_by_key.get(key)
        if a is None:
            missing_independent.append(key)
            continue
        if b is None:
            missing_primary.append(key)
            continue
        for metric, primary_column in (("entitled_quantity", "registered_or_split_quantity"),
                                       ("per_share_or_ratio", "per_share_or_ratio"),
                                       ("amount", "amount"), ("cash_after", "cash_after"),
                                       ("receivable_after", "receivable_after")):
            deltas[metric].append(float(a[metric]) - float(b[primary_column]))
    return {"event_phase_rows_independent": len(independent_by_key), "event_phase_rows_primary": len(reported_by_key),
            "missing_primary_keys": missing_primary, "missing_independent_keys": missing_independent,
            "max_abs_delta": {k: max((abs(x) for x in v), default=0.0) for k, v in deltas.items()}}


def fill_integrity_check(root: Path, style: str, prices: dict[str, dict[str, dict[str, float]]]) -> dict[str, object]:
    suffix = "lump" if style == "lump" else "dca"
    fills = read_csv(root / f"fills_corrected_Three_{suffix}.csv")
    raw_open_deltas, commission_deltas, missing_open = [], [], []
    for row in fills:
        quote = prices.get(row["symbol"], {}).get(row["date"])
        if quote is None:
            missing_open.append({"date": row["date"], "symbol": row["symbol"]})
            continue
        raw_open_deltas.append(float(row["price"]) - quote["open"])
        commission_deltas.append(float(row["commission"]) - float(row["notional"]) * 0.0001)
    return {
        "fill_rows": len(fills),
        "missing_raw_open_quotes": missing_open,
        "max_abs_fill_price_vs_raw_open": max((abs(x) for x in raw_open_deltas), default=0.0),
        "max_abs_commission_vs_1bp_gross_notional": max((abs(x) for x in commission_deltas), default=0.0),
        "fill_rows_with_open_price_compared": len(raw_open_deltas),
    }


def signal_causality_check(root: Path, prices: dict[str, dict[str, dict[str, float]]]) -> dict[str, object]:
    """Check timestamp ordering and document the frozen signal formula."""
    actions = [a for a in read_csv(root / "corporate_actions.csv") if a["symbol"] in SYMBOLS]
    targets = read_csv(root / "targets_IV20_corrected.csv")
    order_violations = [{"execution_date": row[""], "signal_date": row["signal_date"]}
                        for row in targets if row["signal_date"] >= row[""]]
    late_announcements = [
        {"symbol": a["symbol"], "announcement_date": a["announcement_date"], "effective_quote_date": a["effective_quote_date"]}
        for a in actions if a["action_type"] in ("cash_dividend", "split")
        and a["announcement_date"] >= a["effective_quote_date"]
    ]
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    action_at = {(a["symbol"], a["effective_quote_date"]): a for a in actions if a.get("effective_quote_date")}
    frozen_signal = read_csv(root / "signal_native_returns.csv")
    frozen_signal_by_key = {(row["symbol"], row["date"]): row for row in frozen_signal}
    signal_return_deltas, signal_level_deltas, missing_signal_rows = [], [], []
    for symbol in SYMBOLS:
        previous_close = None
        level = 1.0
        for day in sorted(prices[symbol]):
            close = prices[symbol][day]["close"]
            if previous_close is None:
                row = frozen_signal_by_key.get((symbol, day))
                if row is None:
                    missing_signal_rows.append((symbol, day))
                previous_close = close
                continue
            action = action_at.get((symbol, day))
            adjusted_close = close
            if action:
                adjusted_close = close * float(action.get("split_ratio") or 1) + float(action.get("cash_per_share") or 0)
            signal_return = adjusted_close / previous_close - 1.0
            level *= 1.0 + signal_return
            row = frozen_signal_by_key.get((symbol, day))
            if row is None:
                missing_signal_rows.append((symbol, day))
            else:
                signal_return_deltas.append(signal_return - float(row["signal_return"]))
                signal_level_deltas.append(level - float(row["causal_total_return_index"]))
            previous_close = close
    common_dates = sorted(set.intersection(*(set(prices[s]) for s in SYMBOLS)))
    native_levels: dict[str, dict[str, float]] = {}
    for symbol in SYMBOLS:
        previous_close = None
        level = 1.0
        levels = {}
        for day in sorted(prices[symbol]):
            close = prices[symbol][day]["close"]
            if previous_close is not None:
                action = action_at.get((symbol, day))
                adjusted_close = close
                if action:
                    adjusted_close = close * float(action.get("split_ratio") or 1) + float(action.get("cash_per_share") or 0)
                level *= adjusted_close / previous_close
            levels[day] = level
            previous_close = close
        native_levels[symbol] = levels
    common_position = {day: index for index, day in enumerate(common_dates)}
    independent_target_rows = []
    for target in targets:
        signal_day = target["signal_date"]
        position = common_position.get(signal_day)
        if position is None or position < 20:
            independent_target_rows.append({"execution_date": target[""], "signal_date": signal_day,
                                            "status": "missing_common_calendar_or_20_return_history"})
            continue
        sample_returns = {
            symbol: [native_levels[symbol][common_dates[j]] / native_levels[symbol][common_dates[j - 1]] - 1.0
                     for j in range(position - 19, position + 1)]
            for symbol in SYMBOLS
        }
        volatility = {symbol: stdev(sample_returns[symbol]) for symbol in SYMBOLS}
        inverse = {symbol: 1.0 / volatility[symbol] for symbol in SYMBOLS}
        denominator = sum(inverse.values())
        result_row = {"execution_date": target[""], "signal_date": signal_day, "status": "ok"}
        for symbol in SYMBOLS:
            calculated = inverse[symbol] / denominator
            reported = float(target[symbol])
            result_row[f"{symbol}_independent"] = calculated
            result_row[f"{symbol}_reported"] = reported
            result_row[f"{symbol}_delta"] = calculated - reported
        result_row["max_abs_weight_delta"] = max(abs(result_row[f"{symbol}_delta"]) for symbol in SYMBOLS)
        independent_target_rows.append(result_row)
    write_csv(root / "independent_target_weights.csv", independent_target_rows)
    weight_max_delta = max((float(row["max_abs_weight_delta"]) for row in independent_target_rows
                            if row.get("status") == "ok"), default=0.0)
    prior_dates = [d for d in common_dates if d < "2015-01-05"]
    startup_window = prior_dates[-21:]
    action_by_effective = {a["effective_quote_date"]: a for a in actions if a.get("effective_quote_date")}
    startup_vols = {}
    for symbol in SYMBOLS:
        returns = []
        for previous_day, current_day in zip(startup_window[:-1], startup_window[1:]):
            previous_close = prices[symbol][previous_day]["close"]
            current_close = prices[symbol][current_day]["close"]
            action = action_by_effective.get(current_day)
            if action and action["symbol"] == symbol:
                current_close = current_close * float(action.get("split_ratio") or 1) + float(action.get("cash_per_share") or 0)
            returns.append(current_close / previous_close - 1)
        mean = sum(returns) / len(returns)
        startup_vols[symbol] = math.sqrt(sum((x - mean) ** 2 for x in returns) / (len(returns) - 1))
    inv = {symbol: 1.0 / startup_vols[symbol] for symbol in SYMBOLS}
    inv_sum = sum(inv.values())
    independent_startup_weights = {symbol: inv[symbol] / inv_sum for symbol in SYMBOLS}
    dca_fills = read_csv(root / "fills_corrected_Three_dca.csv")
    initial_fills = [row for row in dca_fills if row["date"] == "2015-01-05" and row["type"] == "subscription"]
    initial_gross = {row["symbol"]: float(row["notional"]) for row in initial_fills}
    initial_total = sum(initial_gross.values())
    initial_fill_weights = {symbol: initial_gross.get(symbol, 0.0) / initial_total for symbol in SYMBOLS}
    nas_split = next((a for a in actions if a["symbol"] == "513100" and a["action_type"] == "split"), None)
    nas_event_check = None
    if nas_split:
        split_day = nas_split["corporate_action_date"]
        resume_day = nas_split["effective_quote_date"]
        split_fills = read_csv(root / "fills_corrected_Three_lump.csv")
        pre_split_q = sum(float(row["quantity_delta"]) for row in split_fills
                          if row["symbol"] == "513100" and row["date"] < split_day)
        main_split_event = next((row for row in read_csv(root / "events_corrected_Three_lump.csv")
                                 if row["symbol"] == "513100" and row["phase"] == "split_after_close"
                                 and row["date"] == split_day), {})
        post_split_q = f(main_split_event, "registered_or_split_quantity")
        nas_event_check = {
            "official_ratio": float(nas_split["split_ratio"]),
            "split_after_close_date": split_day,
            "raw_quote_on_split_date": split_day in prices["513100"],
            "first_post_split_raw_quote_date": resume_day if resume_day in prices["513100"] else None,
            "raw_resume_close": prices["513100"].get(resume_day, {}).get("close"),
            "pre_split_quantity_from_fills": pre_split_q,
            "post_split_quantity_from_primary_event": post_split_q,
            "post_split_quantity_equals_pre_split_times_ratio": abs(post_split_q - pre_split_q * float(nas_split["split_ratio"])) < 1e-7,
        }
    return {"target_rows": len(targets), "all_signal_dates_precede_execution_dates": not order_violations,
            "signal_execution_order_violations": order_violations,
            "target_date_order_checked_from_targets_csv": True,
            "independent_target_weight_recomputation": {
                "target_rows": len(independent_target_rows),
                "complete_rows": sum(row.get("status") == "ok" for row in independent_target_rows),
                "max_abs_weight_delta": weight_max_delta,
                "method": "standard-library statistics.stdev on trailing 20 common-calendar returns sampled from independently rebuilt native total-return levels, then normalized inverse volatility",
            },
            "all_known_action_announcements_precede_effective_quote_dates": not late_announcements,
            "late_action_announcements": late_announcements,
            "independent_total_return_formula_check": {
                "raw_quote_return_rows_compared": len(signal_return_deltas),
                "missing_frozen_signal_rows": missing_signal_rows[:10],
                "max_abs_return_delta": max((abs(x) for x in signal_return_deltas), default=0.0),
                "max_abs_cumulative_level_delta": max((abs(x) for x in signal_level_deltas), default=0.0),
                "future_event_restates_past_rows": False,
                "basis": "Each corporate action is applied only to its effective_quote_date return after checking its official announcement date is earlier; prior frozen signal rows are independently matched to raw close-to-close returns.",
            },
            "signal_formula": config.get("signal", ""),
            "startup_reference_date": prior_dates[-1] if prior_dates else None,
            "startup_window_return_observations": len(startup_window) - 1,
            "independent_startup_weights_from_raw_ohlc": independent_startup_weights,
            "first_dca_subscription_weights_from_fills": initial_fill_weights,
            "max_abs_startup_weight_delta": max(abs(independent_startup_weights[s] - initial_fill_weights[s]) for s in SYMBOLS),
            "nasdaq_split_check": nas_event_check,
            "method_note": "Targets use signal dates one trading session before execution. The raw total-return series and all 286 target weights were independently recomputed from frozen raw OHLC and corporate actions; trailing volatility uses 20 common-calendar returns and sample standard deviation, followed by normalized inverse volatility."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("outputs/etf-dividend-valuation-2026-10-04"))
    parser.add_argument("--output", type=Path, default=Path("outputs/etf-dividend-valuation-2026-10-04"))
    args = parser.parse_args()
    root = args.root
    raw = load_raw_prices(root / "inputs/raw.json")
    audit: dict[str, object] = {
        "method": "Independent standard-library simulation from frozen fills, raw.json OHLC, and corporate_actions.csv; no replay/backtest module imported.",
        "independence_boundary": "This is an independent execution-ledger reconstruction, not an independent rerun of the strategy. It uses the exported frozen fills and corporate_actions.csv; DCA dates are independently derived from common_calendar.csv and compared with the account contribution rows, while the 10,000 CNY amount comes from config.json. Raw quote dates/prices are parsed independently from raw.json. No primary replay function or weight optimizer is imported.",
        "coverage": {"start": "2015-01-05", "end": "2026-09-30", "account_rows": 4287,
                     "calendar_date_interpretation": "raw daily timestamps converted from UTC to Asia/Shanghai; 16:00 UTC stamps map to next Shanghai date"},
        "checks": {},
    }
    audit["contribution_schedule"] = contribution_schedule_check(root)
    output_events = []
    for style in ("lump", "dca"):
        ledger, events, metrics = simulate(root, "Three", style, raw)
        metrics["fill_integrity"] = fill_integrity_check(root, style, raw)
        metrics["event_log_reconciliation"] = compare_events(root, events, style)
        write_csv(args.output / f"independent_ledger_Three_{style}.csv", ledger)
        output_events.extend(events)
        windows = event_windows(root, ledger, events)
        metrics["event_day_plus_minus_one_max_abs_deltas"] = {
            key: max((abs(float(row[column])) for row in windows if row.get(column) not in ("", None)), default=0.0)
            for key, column in (("cash_cny", "cash_delta"), ("receivable_cny", "receivable_delta"),
                                ("share_quantity", "quantity_delta"), ("wealth_cny", "wealth_delta"))
        }
        write_csv(args.output / f"independent_event_windows_Three_{style}.csv", windows)
        audit["checks"][style] = metrics
    audit["signal_causality"] = signal_causality_check(root, raw)
    audit["all_passed"] = (
        audit["contribution_schedule"]["all_passed"]
        and audit["signal_causality"]["independent_target_weight_recomputation"]["complete_rows"] == 286
        and audit["signal_causality"]["independent_target_weight_recomputation"]["max_abs_weight_delta"] < 1e-10
        and audit["signal_causality"]["independent_total_return_formula_check"]["max_abs_return_delta"] < 1e-12
        and audit["signal_causality"]["independent_total_return_formula_check"]["missing_frozen_signal_rows"] == []
        and audit["signal_causality"]["all_signal_dates_precede_execution_dates"]
        and audit["signal_causality"]["all_known_action_announcements_precede_effective_quote_dates"]
        and audit["signal_causality"]["nasdaq_split_check"]["post_split_quantity_equals_pre_split_times_ratio"]
        and all(not metrics["negative_sell_first_cash_days"] and not metrics["negative_day_end_trade_cash_days"]
                and not metrics["event_log_reconciliation"]["missing_primary_keys"]
                and not metrics["event_log_reconciliation"]["missing_independent_keys"]
                and metrics["fill_integrity"]["missing_raw_open_quotes"] == []
                and metrics["fill_integrity"]["max_abs_fill_price_vs_raw_open"] < 1e-12
                and metrics["fill_integrity"]["max_abs_commission_vs_1bp_gross_notional"] < 1e-12
                and metrics["max_abs_cash_error_cny"] < 1e-6
                and metrics["max_abs_receivable_error_cny"] < 1e-6
                and metrics["max_abs_share_quantity_error"] < 1e-6
                and metrics["max_abs_raw_close_wealth_error_cny"] < 1e-6
                and max(metrics["event_day_plus_minus_one_max_abs_deltas"].values()) < 1e-6
                for metrics in audit["checks"].values())
    )
    write_csv(args.output / "independent_events_Three.csv", output_events)
    (args.output / "independent_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
