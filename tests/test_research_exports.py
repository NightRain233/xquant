import pandas as pd
import pytest

from xquant.research_exports import build_recent_monthly_records


AS_OF = pd.Timestamp("2026-06-27")
ASSET_NAMES = {"AAA": "资产 A", "CASH": "现金"}


def make_nav() -> pd.Series:
    return pd.Series(
        [
            100.0,
            104.0,
            110.0,
            115.0,
            121.0,
            118.0,
            125.0,
            130.0,
        ],
        index=pd.to_datetime(
            [
                "2025-12-31",
                "2026-01-15",
                "2026-01-30",
                "2026-02-27",
                "2026-03-31",
                "2026-04-30",
                "2026-05-29",
                "2026-06-26",
            ]
        ),
        name="nav",
    )


def make_executed_weights() -> pd.DataFrame:
    dates: list[str] = []
    rows: list[dict[str, float]] = []
    for month in range(1, 7):
        dates.extend([f"2026-{month:02d}-05", f"2026-{month:02d}-20"])
        rows.extend(
            [
                {"AAA": 0.4, "CASH": 0.6},
                {"AAA": month / 10, "CASH": 1 - month / 10},
            ]
        )
    return pd.DataFrame(rows, index=pd.to_datetime(dates))


def test_builds_six_recent_calendar_months_in_chronological_order() -> None:
    records = build_recent_monthly_records(
        "candidate",
        make_nav(),
        make_executed_weights(),
        ASSET_NAMES,
        as_of=AS_OF,
    )

    assert records["month"].tolist() == [
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
    ]
    assert records["month_end_date"].tolist()[-1] == "2026-06-26"


def test_monthly_returns_use_last_nav_value_in_each_month() -> None:
    records = build_recent_monthly_records(
        "candidate",
        make_nav(),
        make_executed_weights(),
        ASSET_NAMES,
        as_of=AS_OF,
    )

    assert records["return"].tolist() == pytest.approx(
        [
            110 / 100 - 1,
            115 / 110 - 1,
            121 / 115 - 1,
            118 / 121 - 1,
            125 / 118 - 1,
            130 / 125 - 1,
        ]
    )


def test_holdings_use_last_executed_weight_row_in_each_month() -> None:
    records = build_recent_monthly_records(
        "candidate",
        make_nav(),
        make_executed_weights(),
        ASSET_NAMES,
        as_of=AS_OF,
    )

    assert records["资产 A"].tolist() == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    assert records["现金"].tolist() == pytest.approx([0.9, 0.8, 0.7, 0.6, 0.5, 0.4])


def test_only_latest_current_calendar_month_is_partial() -> None:
    records = build_recent_monthly_records(
        "candidate",
        make_nav(),
        make_executed_weights(),
        ASSET_NAMES,
        as_of=AS_OF,
    )

    assert records["is_partial"].tolist() == [False, False, False, False, False, True]


def test_every_returned_holding_row_sums_to_one() -> None:
    records = build_recent_monthly_records(
        "candidate",
        make_nav(),
        make_executed_weights(),
        ASSET_NAMES,
        as_of=AS_OF,
    )

    assert records[["资产 A", "现金"]].sum(axis=1).tolist() == pytest.approx([1.0] * 6)


def test_rejects_empty_nav() -> None:
    with pytest.raises(ValueError, match="NAV must not be empty"):
        build_recent_monthly_records(
            "candidate",
            pd.Series(dtype=float),
            make_executed_weights(),
            ASSET_NAMES,
            as_of=AS_OF,
        )


def test_rejects_month_without_executed_weights() -> None:
    weights = make_executed_weights().drop(pd.Timestamp("2026-03-05")).drop(pd.Timestamp("2026-03-20"))

    with pytest.raises(ValueError, match="Missing executed weights for 2026-03"):
        build_recent_monthly_records("candidate", make_nav(), weights, ASSET_NAMES, as_of=AS_OF)


@pytest.mark.parametrize("duplicate_source", ["nav", "weights"])
def test_rejects_duplicate_dates(duplicate_source: str) -> None:
    nav = make_nav()
    weights = make_executed_weights()
    if duplicate_source == "nav":
        nav = pd.concat([nav, nav.iloc[[-1]]])
    else:
        weights = pd.concat([weights, weights.iloc[[-1]]])

    with pytest.raises(ValueError, match="duplicate dates"):
        build_recent_monthly_records("candidate", nav, weights, ASSET_NAMES, as_of=AS_OF)


def test_rejects_holdings_that_do_not_sum_to_one() -> None:
    weights = make_executed_weights()
    weights.loc[pd.Timestamp("2026-04-20"), "CASH"] = 0.5

    with pytest.raises(ValueError, match="Holdings for 2026-04 must sum to one"):
        build_recent_monthly_records("candidate", make_nav(), weights, ASSET_NAMES, as_of=AS_OF)
