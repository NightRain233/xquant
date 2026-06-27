import pandas as pd
import pytest

from xquant.portfolio import (
    apply_weight_cap,
    inverse_volatility_weights,
    normalize_weights,
)


def test_normalize_weights_clips_negative_values_and_allocates_cash():
    weights = normalize_weights({"A": 0.3, "B": -0.2}, ["A", "B"])

    assert weights == {"A": 0.3, "B": 0.0, "CASH": 0.7}


def test_normalize_weights_scales_down_overallocated_assets():
    weights = normalize_weights({"A": 0.8, "B": 0.4}, ["A", "B"])

    assert weights["A"] == pytest.approx(2 / 3)
    assert weights["B"] == pytest.approx(1 / 3)
    assert weights["CASH"] == pytest.approx(0.0)


def test_apply_weight_cap_redistributes_excess_proportionally():
    weights = apply_weight_cap({"A": 0.8, "B": 0.1, "C": 0.1}, ["A", "B", "C"], cap=0.5)

    assert weights == pytest.approx({"A": 0.5, "B": 0.25, "C": 0.25, "CASH": 0.0})


def test_apply_weight_cap_leaves_cash_when_cap_is_infeasible():
    weights = apply_weight_cap({"A": 0.5, "B": 0.5}, ["A", "B"], cap=0.4)

    assert weights == pytest.approx({"A": 0.4, "B": 0.4, "CASH": 0.2})


def test_inverse_volatility_weights_favors_lower_volatility_assets():
    returns = pd.DataFrame(
        {
            "A": [-0.02, 0.02, -0.02, 0.02],
            "B": [-0.01, 0.01, -0.01, 0.01],
        }
    )

    weights = inverse_volatility_weights(returns, ["A", "B"])

    assert weights == pytest.approx({"A": 1 / 3, "B": 2 / 3, "CASH": 0.0})
