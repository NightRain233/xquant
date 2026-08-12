from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "paper-tracking-oos-2026-06-27"
FREEZE_DATE = pd.Timestamp("2026-06-26")
TRADING_DAYS = 252


@dataclass(frozen=True)
class StrategySource:
    strategy_id: str
    strategy_name: str
    baseline_name: str
    path: Path
    strategy_column: str
    baseline_column: str
    return_basis: str


SOURCES = (
    StrategySource(
        strategy_id="btc-supertrend-7.5",
        strategy_name="BTC 7.5% SuperTrend 卫星",
        baseline_name="原三资产 RiskParity",
        path=PROJECT_ROOT / "outputs" / "q10-live-readiness-stress" / "paper_execution_nav.csv",
        strategy_column="BTC7.5%_next_close",
        baseline_column="RP_next_close",
        return_basis="next-close net, 20 bps cost plus 10 bps slippage, 1% threshold",
    ),
    StrategySource(
        strategy_id="theme-alpha-def200-cash",
        strategy_name="Theme Alpha Def200 Cash 双月调仓",
        baseline_name="Theme Alpha Base 双月调仓",
        path=(
            PROJECT_ROOT
            / "outputs"
            / "theme-alpha-q8-signal-live-readiness"
            / "nav_q8_selected_2021_to_date.csv"
        ),
        strategy_column="Def200 Bimonthly",
        baseline_column="Base Bimonthly",
        return_basis="next-close net, base 20 bps plus asset friction",
    ),
)


def load_oos_nav(source: StrategySource) -> pd.DataFrame:
    nav = pd.read_csv(source.path, index_col=0, parse_dates=True, encoding="utf-8-sig")
    nav.index = pd.DatetimeIndex(nav.index).tz_localize(None).normalize()
    required = [source.strategy_column, source.baseline_column]
    missing = [column for column in required if column not in nav.columns]
    if missing:
        raise ValueError(f"{source.path} missing columns: {missing}")
    if FREEZE_DATE not in nav.index:
        raise ValueError(f"{source.path} does not contain freeze date {FREEZE_DATE.date()}")

    selected = nav.loc[FREEZE_DATE:, required].dropna()
    if len(selected) < 2:
        raise ValueError(f"{source.path} has no observations after the freeze date")
    normalized = selected.div(selected.iloc[0]).mul(100.0)
    normalized.columns = ["strategy", "baseline"]
    return normalized


def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1.0).min())


def summarize(source: StrategySource, nav: pd.DataFrame) -> dict[str, object]:
    strategy_returns = nav["strategy"].pct_change().dropna()
    baseline_returns = nav["baseline"].pct_change().dropna()
    trading_days = len(strategy_returns)
    strategy_total = float(nav["strategy"].iloc[-1] / nav["strategy"].iloc[0] - 1.0)
    baseline_total = float(nav["baseline"].iloc[-1] / nav["baseline"].iloc[0] - 1.0)
    annualized_return = (1.0 + strategy_total) ** (TRADING_DAYS / trading_days) - 1.0
    annualized_volatility = float(strategy_returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
    sharpe = (
        float(strategy_returns.mean() * TRADING_DAYS / annualized_volatility)
        if annualized_volatility > 0
        else np.nan
    )
    drawdown = nav["strategy"] / nav["strategy"].cummax() - 1.0
    strategy_max_drawdown = max_drawdown(nav["strategy"])
    baseline_max_drawdown = max_drawdown(nav["baseline"])
    return {
        "strategy_id": source.strategy_id,
        "strategy": source.strategy_name,
        "baseline": source.baseline_name,
        "return_basis": source.return_basis,
        "freeze_date": str(nav.index[0].date()),
        "end_date": str(nav.index[-1].date()),
        "trading_days": trading_days,
        "cumulative_return": strategy_total,
        "baseline_return": baseline_total,
        "excess_return": strategy_total - baseline_total,
        "annualized_return_short_window": annualized_return,
        "annualized_volatility": annualized_volatility,
        "max_drawdown": strategy_max_drawdown,
        "baseline_max_drawdown": baseline_max_drawdown,
        "drawdown_advantage": strategy_max_drawdown - baseline_max_drawdown,
        "current_drawdown": float(drawdown.iloc[-1]),
        "sharpe_short_window": sharpe,
        "positive_day_rate": float((strategy_returns > 0).mean()),
        "best_day": float(strategy_returns.max()),
        "worst_day": float(strategy_returns.min()),
    }


def build_monthly_returns(source: StrategySource, nav: pd.DataFrame) -> pd.DataFrame:
    daily_returns = nav.pct_change().dropna()
    monthly = daily_returns.resample("ME").apply(lambda values: (1.0 + values).prod() - 1.0)
    monthly = monthly.rename(columns={"strategy": "strategy_return", "baseline": "baseline_return"})
    monthly["excess_return"] = monthly["strategy_return"] - monthly["baseline_return"]
    monthly.insert(0, "month", monthly.index.to_period("M").astype(str))
    monthly.insert(0, "strategy_id", source.strategy_id)
    return monthly.reset_index(names="month_end_date")


def build_daily_nav(source: StrategySource, nav: pd.DataFrame) -> pd.DataFrame:
    out = nav.copy()
    out.insert(0, "strategy_id", source.strategy_id)
    return out.reset_index(names="date")


def build_latest_status() -> pd.DataFrame:
    q10_dir = PROJECT_ROOT / "outputs" / "q10-live-readiness-stress"
    theme_dir = PROJECT_ROOT / "outputs" / "theme-alpha-q8-signal-live-readiness"

    btc_signal = pd.read_csv(
        q10_dir / "latest_signal_summary.csv", index_col=0, encoding="utf-8-sig"
    ).iloc[:, 0]
    btc_targets = pd.read_csv(
        q10_dir / "latest_target_weights.csv", index_col=0, encoding="utf-8-sig"
    ).loc["BTC7.5%ST卫星"]

    theme_snapshot = pd.read_csv(
        theme_dir / "paper_tracking_snapshot.csv", encoding="utf-8-sig"
    ).iloc[0]
    theme_targets = pd.read_csv(
        theme_dir / "latest_target_weights.csv", encoding="utf-8-sig"
    )
    theme_target = theme_targets[
        theme_targets["candidate"].eq("Def200_Cash")
        & theme_targets["schedule"].eq("BIMONTHLY")
    ].iloc[0]

    rows = [
        {
            "strategy_id": "btc-supertrend-7.5",
            "market_data_date": str(btc_signal["latest_date"]),
            "signal_date": str(btc_signal["latest_date"]),
            "execution_date": "",
            "signal": "ON" if str(btc_signal["btc_supertrend_on"]).lower() == "true" else "OFF",
            "cash_weight": float(btc_targets["CASH"]),
            "target_weights": "; ".join(
                f"{asset}={float(weight):.6f}" for asset, weight in btc_targets.items()
            ),
        },
        {
            "strategy_id": "theme-alpha-def200-cash",
            "market_data_date": str(theme_snapshot["market_data_date"]),
            "signal_date": str(theme_snapshot["signal_date"]),
            "execution_date": (
                "" if pd.isna(theme_snapshot["execution_date"])
                else str(theme_snapshot["execution_date"])
            ),
            "signal": "PENDING_NEXT_TRADE_DAY" if pd.isna(theme_snapshot["execution_date"]) else "EXECUTABLE",
            "cash_weight": float(theme_target["现金"]),
            "target_weights": "; ".join(
                f"{asset}={float(theme_target[asset]):.6f}"
                for asset in theme_targets.columns
                if asset not in {"candidate", "schedule"}
            ),
        },
    ]
    return pd.DataFrame(rows)


def build_btc_execution_comparison() -> pd.DataFrame:
    path = PROJECT_ROOT / "outputs" / "q10-live-readiness-stress" / "paper_execution_nav.csv"
    rows = []
    for execution in ("next_close", "next_open"):
        source = StrategySource(
            strategy_id=f"btc-supertrend-7.5-{execution.replace('_', '-')}",
            strategy_name=f"BTC 7.5% SuperTrend 卫星 ({execution})",
            baseline_name=f"原三资产 RiskParity ({execution})",
            path=path,
            strategy_column=f"BTC7.5%_{execution}",
            baseline_column=f"RP_{execution}",
            return_basis="20 bps cost plus 10 bps slippage, 1% threshold",
        )
        rows.append(summarize(source, load_oos_nav(source)))
    return pd.DataFrame(rows)


def build_btc_trade_summary() -> pd.DataFrame:
    path = PROJECT_ROOT / "outputs" / "q10-live-readiness-stress" / "paper_execution_trades.csv"
    trades = pd.read_csv(path, parse_dates=["date"], encoding="utf-8-sig")
    trades = trades[
        trades["date"].gt(FREEZE_DATE)
        & trades["ledger"].isin(
            ["RP_next_close", "BTC7.5%_next_close", "RP_next_open", "BTC7.5%_next_open"]
        )
    ]
    return (
        trades.groupby("ledger", as_index=False)
        .agg(
            first_trade_date=("date", "min"),
            last_trade_date=("date", "max"),
            trade_count=("date", "size"),
            total_one_way_turnover=("turnover", "sum"),
            total_cost_drag=("cost_drag", "sum"),
        )
        .sort_values("ledger")
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    daily_frames = []
    monthly_frames = []
    for source in SOURCES:
        nav = load_oos_nav(source)
        summaries.append(summarize(source, nav))
        daily_frames.append(build_daily_nav(source, nav))
        monthly_frames.append(build_monthly_returns(source, nav))

    pd.DataFrame(summaries).to_csv(
        OUTPUT_DIR / "summary.csv", index=False, encoding="utf-8-sig"
    )
    pd.concat(daily_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "daily_nav.csv", index=False, encoding="utf-8-sig"
    )
    pd.concat(monthly_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "monthly_returns.csv", index=False, encoding="utf-8-sig"
    )
    build_latest_status().to_csv(
        OUTPUT_DIR / "latest_status.csv", index=False, encoding="utf-8-sig"
    )
    build_btc_execution_comparison().to_csv(
        OUTPUT_DIR / "btc_execution_comparison.csv", index=False, encoding="utf-8-sig"
    )
    build_btc_trade_summary().to_csv(
        OUTPUT_DIR / "btc_trade_summary.csv", index=False, encoding="utf-8-sig"
    )


if __name__ == "__main__":
    main()
