import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "theme_alpha_q12_long_sample_proxy_validation.py"
SPEC = importlib.util.spec_from_file_location("theme_alpha_q12_long_sample_proxy_validation", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


def test_script_uses_expected_low_vol_trend_and_risk_parity_behavior():
    index = pd.date_range("2026-01-01", periods=70)
    step = np.arange(70)
    close = pd.DataFrame(
        {
            "A": np.linspace(100, 112, 70),
            "B": np.linspace(100, 120, 70) + np.sin(step) * 4,
            "C": np.linspace(100, 116, 70) + np.sin(step) * 0.4,
        },
        index=index,
    )
    returns = close.pct_change()
    market = {"close": close, "returns": returns}

    selected = study.low_vol_trend_select(market, close.columns, index[-1])
    weights = study.risk_parity_weight(market, index[-1], ["A", "C"], close.columns, cap=0.6)

    assert selected == ["A", "C", "B"]
    assert sum(weights.values()) == pytest.approx(1.0)
    assert max(weights["A"], weights["C"]) <= 0.6
    assert weights["B"] == 0.0


def test_script_nav_and_drawdown_keep_the_experiment_initial_value():
    returns = pd.Series([0.0, -0.1, 1 / 9])

    nav = study.nav_from_returns(returns)
    drawdown = study.drawdown_series(nav)

    assert nav.tolist() == pytest.approx([100.0, 90.0, 100.0])
    assert drawdown.tolist() == pytest.approx([0.0, -0.1, 0.0])
