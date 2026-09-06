"""Create dated, non-destructive evidence for the Theme Alpha Def200 review.

This script does not generate a new strategy or rewrite any frozen research.
It reads the frozen Q8 target weights and compares them with dated OHLCV from
the trading checkout for a next-close execution measurement.  The small
capital calculation uses integer ETF lots and explicit commission scenarios.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TRADING_ROOT = Path("/Users/zz/Desktop/Code/zsd/trading")
DATA_ROOT = TRADING_ROOT / "backend" / "data"
OUTPUT_ROOT = ROOT / "outputs" / "def200-cash-manual-review-2026-09-06"
Q8_ROOT = ROOT / "outputs" / "theme-alpha-q8-signal-live-readiness"

ASSET_COLUMNS = {
    "沪深300ETF": "510300.SS",
    "纳指100ETF": "513100.SS",
    "黄金ETF": "518880.SS",
    "有色金属ETF": "512400.SS",
    "芯片ETF": "159995.SZ",
    "通信ETF": "515880.SS",
    "红利ETF": "510880.SS",
    "能源ETF": "159930.SZ",
    "证券ETF": "512880.SS",
    "恒生科技ETF": "513180.SS",
    "医疗ETF": "512170.SS",
}
LOT_SIZE = 100
CAPITALS = (3_000.0, 5_000.0)
COMMISSION_RATES = (0.0000, 0.0002, 0.0005, 0.0010)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def next_xshg_session(signal_date: pd.Timestamp) -> pd.Timestamp:
    from portfolio_strategies.schedules import xshg_sessions

    sessions = xshg_sessions(signal_date.date(), date(2026, 8, 19))
    future = sessions[sessions > signal_date]
    if future.empty:
        raise ValueError("No next XSHG session is available in the dated price data")
    return future[0]


def load_frozen_target() -> tuple[pd.Series, pd.Series, pd.Timestamp, pd.Timestamp]:
    target = pd.read_csv(Q8_ROOT / "latest_target_weights.csv", encoding="utf-8-sig")
    row = target[
        target["candidate"].eq("Def200_Cash")
        & target["schedule"].eq("BIMONTHLY")
    ]
    if len(row) != 1:
        raise ValueError("Expected exactly one frozen Def200 Cash BIMONTHLY row")
    row = row.iloc[0]
    snapshot = pd.read_csv(
        Q8_ROOT / "paper_tracking_snapshot.csv", encoding="utf-8-sig"
    ).iloc[0]
    market_date = pd.Timestamp(snapshot["market_data_date"])
    signal_date = pd.Timestamp(snapshot["signal_date"])
    weights = pd.Series(
        {symbol: float(row[column]) for column, symbol in ASSET_COLUMNS.items()}
    )
    weights["CASH"] = float(row["现金"])
    if not math.isclose(float(weights.sum()), 1.0, abs_tol=1e-10):
        raise ValueError("Frozen target weights do not sum to one")
    return weights, snapshot, market_date, signal_date


def load_prices(symbols: list[str], signal_date: pd.Timestamp, execution_date: pd.Timestamp):
    rows = []
    for symbol in symbols:
        path = DATA_ROOT / f"{symbol}.parquet"
        if not path.exists():
            raise FileNotFoundError(path)
        frame = pd.read_parquet(path)
        for required_date in (signal_date, execution_date):
            if required_date not in frame.index:
                raise ValueError(f"{symbol} has no dated row for {required_date.date()}")
        signal = frame.loc[signal_date]
        execution = frame.loc[execution_date]
        source_path = DATA_ROOT / f"{symbol}.parquet.source.json"
        source = json.loads(source_path.read_text()) if source_path.exists() else {}
        rows.append(
            {
                "symbol": symbol,
                "signal_date": signal_date.date().isoformat(),
                "signal_close": float(signal["Close"]),
                "execution_date": execution_date.date().isoformat(),
                "execution_open": float(execution["Open"]),
                "execution_close": float(execution["Close"]),
                "execution_volume": float(execution["Volume"]),
                "source_version": source.get("sourceVersion", "unknown"),
                "source_last_full_refresh_at": source.get("lastFullRefreshAt", ""),
                "source_last_incremental_refresh_at": source.get(
                    "lastIncrementalRefreshAt", ""
                ),
                "positive_ohlc": all(
                    math.isfinite(float(execution[field])) and float(execution[field]) > 0
                    for field in ("Open", "High", "Low", "Close")
                ),
                "positive_volume": math.isfinite(float(execution["Volume"]))
                and float(execution["Volume"]) > 0,
                "signal_to_execution_open_pct": float(execution["Open"])
                / float(signal["Close"])
                - 1.0,
                "signal_to_execution_close_pct": float(execution["Close"])
                / float(signal["Close"])
                - 1.0,
                "execution_open_to_close_pct": float(execution["Close"])
                / float(execution["Open"])
                - 1.0,
                "premium_discount_check": "not available from OHLCV; check broker/official iNAV manually",
            }
        )
    return pd.DataFrame(rows)


def build_lot_scenarios(weights: pd.Series, prices: pd.DataFrame) -> pd.DataFrame:
    price_by_symbol = prices.set_index("symbol")["execution_close"].to_dict()
    rows = []
    for capital in CAPITALS:
        quantities = {}
        notionals = {}
        for symbol, weight in weights.items():
            if symbol == "CASH" or weight <= 0:
                continue
            target_amount = capital * float(weight)
            price = float(price_by_symbol[symbol])
            quantity = math.floor(target_amount / (price * LOT_SIZE)) * LOT_SIZE
            quantities[symbol] = quantity
            notionals[symbol] = quantity * price
        gross_notional = sum(notionals.values())
        residual_before_fee = capital - gross_notional
        for commission_rate in COMMISSION_RATES:
            commission = gross_notional * commission_rate
            cash = residual_before_fee - commission
            post_fee_nav = capital - commission
            for symbol, weight in weights.items():
                if symbol == "CASH":
                    actual_weight = cash / post_fee_nav
                    quantity = 0
                    notional = 0.0
                    price = 1.0
                elif float(weight) <= 0.0:
                    actual_weight = 0.0
                    quantity = 0
                    notional = 0.0
                    price = None
                else:
                    quantity = quantities.get(symbol, 0)
                    notional = notionals.get(symbol, 0.0)
                    price = price_by_symbol[symbol]
                    actual_weight = notional / post_fee_nav
                rows.append(
                    {
                        "capital": capital,
                        "commission_rate_one_way": commission_rate,
                        "commission_budget": commission,
                        "post_fee_nav": post_fee_nav,
                        "symbol": symbol,
                        "target_weight": float(weight),
                        "target_amount": capital * float(weight),
                        "price_used": price,
                        "lot_size": LOT_SIZE,
                        "quantity": quantity,
                        "notional": notional,
                        "actual_weight": actual_weight,
                        "weight_error": actual_weight - float(weight),
                        "cash_after_fee": cash if symbol == "CASH" else None,
                        "cash_sufficient_for_commission": cash >= -1e-9,
                        "max_commission_rate_before_cash_shortfall": (
                            residual_before_fee / gross_notional
                            if gross_notional > 0
                            else None
                        ),
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    weights, snapshot, market_date, signal_date = load_frozen_target()
    execution_date = next_xshg_session(signal_date)
    symbols = [symbol for symbol, weight in weights.items() if symbol != "CASH" and weight > 0]
    prices = load_prices(symbols, signal_date, execution_date)
    if not bool(prices["positive_ohlc"].all() and prices["positive_volume"].all()):
        raise ValueError("A target asset has missing or non-tradable dated OHLCV")

    prices.to_csv(OUTPUT_ROOT / "execution_price_check.csv", index=False, encoding="utf-8-sig")
    lot_scenarios = build_lot_scenarios(weights, prices)
    lot_scenarios.to_csv(
        OUTPUT_ROOT / "small_capital_lot_scenarios.csv",
        index=False,
        encoding="utf-8-sig",
    )
    weights.rename("target_weight").to_frame().to_csv(
        OUTPUT_ROOT / "frozen_def200_target_weights.csv",
        encoding="utf-8-sig",
    )

    source_files = [
        ROOT / "docs" / "notes" / "theme-alpha-q8-signal-live-readiness-review.md",
        ROOT / "docs" / "notes" / "theme-alpha-q12-long-sample-proxy-validation-review.md",
        Q8_ROOT / "latest_target_weights.csv",
        Q8_ROOT / "latest_sleeve_weights.csv",
        Q8_ROOT / "paper_tracking_snapshot.csv",
        TRADING_ROOT / "backend" / "portfolio_strategies" / "theme_alpha.py",
        TRADING_ROOT / "backend" / "portfolio_strategies" / "paper_engine.py",
        TRADING_ROOT / "backend" / "portfolio_strategies" / "registry.py",
        TRADING_ROOT / "backend" / "portfolio_strategies" / "indicators.py",
        TRADING_ROOT / "backend" / "portfolio_strategies" / "schedules.py",
    ]
    manifest = {
        "createdAt": "2026-09-06",
        "purpose": "Non-destructive Def200 Cash implementation and small-capital review",
        "strategyIdentity": "Core80 + Expanded LVT20 + Def200 Cash",
        "notAnOrder": True,
        "sourceRepositories": {
            "xquant": {"path": str(ROOT), "commit": git_head(ROOT)},
            "trading": {"path": str(TRADING_ROOT), "commit": git_head(TRADING_ROOT)},
        },
        "frozenSnapshot": {
            "marketDataDate": str(snapshot["market_data_date"]),
            "signalDate": str(snapshot["signal_date"]),
            "executionDateUsedForFeasibility": execution_date.date().isoformat(),
            "targetWeightsSum": float(weights.sum()),
            "researchPriceConvention": "Q8 yfinance auto_adjust=True Close; adjusted research proxy",
            "executionPriceConvention": "trading TickFlow parquet OHLCV; next-session Close measurement",
        },
        "lotRule": {
            "lotSize": LOT_SIZE,
            "rule": "Buy quantity floored to 100-share lots; no ETF substitution or extra funding",
        },
        "commissionScenarios": list(COMMISSION_RATES),
        "sourceFileSha256": {str(path): sha256(path) for path in source_files},
        "limitations": [
            "Q8 adjusted Close values are not retained per order; exact adjusted-vs-tradable price spread cannot be reconstructed.",
            "OHLCV does not contain ETF premium/discount or iNAV; broker/official fund page check remains required.",
            "The local trading cache has a later source date but this measurement is deliberately fixed to signal 2026-08-10 and next session 2026-08-11.",
            "Commission scenarios exclude any broker-specific non-commission fees until confirmed.",
        ],
    }
    (OUTPUT_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )

    implementation_audit = {
        "strategyIdentity": {
            "A_pure_three_asset_risk_parity": "Paper comparison only; not the target live candidate.",
            "B_pure_three_asset_plus_def200_cash": "No independent frozen research-and-implementation contract found in the reviewed artifacts; do not infer it from C.",
            "C_core80_lvt20_def200_cash": "Existing Q6-Q12 research candidate and trading theme_alpha implementation; target of this review.",
        },
        "execution": {
            "signalDate": signal_date.date().isoformat(),
            "executionDate": execution_date.date().isoformat(),
            "isAfterSignal": execution_date > signal_date,
            "contract": "next_close",
        },
        "dataChecks": {
            "allTargetAssetsHavePositiveOHLC": bool(prices["positive_ohlc"].all()),
            "allTargetAssetsHavePositiveVolume": bool(prices["positive_volume"].all()),
            "noSuspensionInMeasuredRows": bool(prices["positive_volume"].all()),
            "premiumDiscountVerified": False,
        },
        "researchResults": {
            "frozenQ8OutputsPreserved": True,
            "oldQ8SimulatorIsLatestUnifiedLedgerAudit": False,
            "reason": "Q8 uses persistent weight rows and adjusted Close research prices; trading values actual quantities at execution close.",
        },
    }
    (OUTPUT_ROOT / "implementation_audit.json").write_text(
        json.dumps(implementation_audit, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
