from collections.abc import Mapping

import numpy as np
import pandas as pd


def build_recent_monthly_records(
    strategy: str,
    nav: pd.Series,
    executed_weights: pd.DataFrame,
    asset_names: Mapping[str, str],
    *,
    count: int = 6,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build recent calendar-month returns and executed month-end holdings."""
    if nav.empty:
        raise ValueError("NAV must not be empty")
    if count <= 0:
        raise ValueError("count must be positive")

    nav = nav.copy()
    executed_weights = executed_weights.copy()
    nav.index = pd.DatetimeIndex(nav.index)
    executed_weights.index = pd.DatetimeIndex(executed_weights.index)

    if nav.index.has_duplicates:
        raise ValueError("NAV contains duplicate dates")
    if executed_weights.index.has_duplicates:
        raise ValueError("Executed weights contain duplicate dates")

    cutoff = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.today().normalize()
    nav = nav.loc[nav.index <= cutoff].sort_index()
    executed_weights = executed_weights.loc[executed_weights.index <= cutoff].sort_index()
    if nav.empty:
        raise ValueError("NAV must not be empty as of the requested date")

    nav_months = nav.index.to_period("M")
    month_end_nav = nav.groupby(nav_months, sort=True).tail(1)
    monthly_returns = month_end_nav.pct_change(fill_method=None).dropna().tail(count)
    if len(monthly_returns) < count:
        raise ValueError(f"NAV must contain enough month-end values for {count} monthly returns")

    selected_dates = monthly_returns.index
    selected_months = selected_dates.to_period("M")
    named_assets = [asset_names.get(str(asset), str(asset)) for asset in executed_weights.columns]
    if len(named_assets) != len(set(named_assets)):
        raise ValueError("Asset names must be unique")

    holding_rows: list[pd.Series] = []
    weight_months = executed_weights.index.to_period("M")
    for month, month_end_date in zip(selected_months, selected_dates, strict=True):
        month_weights = executed_weights.loc[(weight_months == month) & (executed_weights.index <= month_end_date)]
        if month_weights.empty:
            raise ValueError(f"Missing executed weights for {month}")

        holdings = pd.to_numeric(month_weights.iloc[-1], errors="raise")
        if not np.isfinite(holdings.to_numpy(dtype=float)).all():
            raise ValueError(f"Holdings for {month} must be finite")
        if not np.isclose(float(holdings.sum()), 1.0, rtol=0.0, atol=1e-8):
            raise ValueError(f"Holdings for {month} must sum to one")
        holdings.index = named_assets
        holding_rows.append(holdings)

    current_month = cutoff.to_period("M")
    records = pd.DataFrame(
        {
            "strategy": strategy,
            "month": selected_months.astype(str),
            "month_end_date": selected_dates.strftime("%Y-%m-%d"),
            "is_partial": [month == current_month for month in selected_months],
            "return": monthly_returns.to_numpy(dtype=float),
        }
    )
    holdings_frame = pd.DataFrame(holding_rows).reset_index(drop=True)
    return pd.concat([records, holdings_frame], axis=1)
