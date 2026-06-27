import pandas as pd
import pytest

from xquant.metrics import drawdown_series, nav_from_returns


def test_nav_from_returns_compounds_from_initial_capital():
    returns = pd.Series([0.0, 0.1, -0.1])

    nav = nav_from_returns(returns, initial_capital=100.0)

    assert nav.tolist() == pytest.approx([100.0, 110.0, 99.0])


def test_drawdown_uses_initial_capital_as_the_first_peak():
    nav = pd.Series([90.0, 95.0, 100.0, 80.0, 110.0])

    drawdown = drawdown_series(nav, initial_capital=100.0)

    assert drawdown.tolist() == pytest.approx([-0.1, -0.05, 0.0, -0.2, 0.0])


def test_drawdown_returns_empty_input_unchanged():
    nav = pd.Series(dtype=float)

    drawdown = drawdown_series(nav)

    assert drawdown.empty


def test_drawdown_resets_after_reaching_a_new_high():
    nav = pd.Series([100.0, 80.0, 120.0, 108.0])

    drawdown = drawdown_series(nav)

    assert drawdown.tolist() == pytest.approx([0.0, -0.2, 0.0, -0.1])
