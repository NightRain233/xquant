"""Contract and integrity tests for the 2026-11-23 gold quantitative enhancement study."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "outputs" / "gold-enhance-2026-11-23"


def test_gold_enhance_self_checks_and_key_artifacts():
    assert OUT_DIR.exists(), "gold-enhance-2026-11-23 output directory missing"
    checks = json.loads((OUT_DIR / "self_checks.json").read_text(encoding="utf-8"))
    assert checks["anti_lookahead_passed"] is True
    assert checks["anti_lookahead_max_diff"] == 0.0
    assert checks["cash_conservation_passed"] is True
    assert checks["max_cash_residual"] < 1e-12
    assert checks["cross_market_lag_passed"] is True
    assert checks["cross_market_min_lag_days"] >= 1
    assert checks["checked_signal_count"] >= 35

    required_csvs = [
        "gold_physics_fingerprint.csv",
        "gold_seasonality_audit.csv",
        "gold_55y_long_cycle.csv",
        "gold_gld_strategies_summary.csv",
        "gold_gld_permutation.csv",
        "gold_ugl_2x_leverage.csv",
        "gold_macro_timing.csv",
        "gold_precious_metals_rotation.csv",
        "gold_cross_asset_shields.csv",
        "gold_dca_rolling.csv",
        "gold_dca_smart_budget_neutral.csv",
        "gold_domestic_518880.csv",
        "gold_crypto_paxg_audit.csv",
        "dd1_tvt_low_turnover_gld.csv",
        "dd1_tvt_param_plateau.csv",
        "dd1_tvt_low_turnover_cn518880.csv",
        "dd2_55y_rate_regimes.csv",
        "dd3_gsr_25y_audit.csv",
        "dd4_gold_btc_regimes.csv",
    ]
    for fname in required_csvs:
        p = OUT_DIR / fname
        assert p.exists(), f"Missing artifact CSV: {fname}"
        df = pd.read_csv(p)
        assert len(df) >= 4, f"Unexpectedly small CSV: {fname}"

    # Verify headline empirical invariants remain intact
    plateau = pd.read_csv(OUT_DIR / "dd1_tvt_param_plateau.csv")
    assert len(plateau) == 140
    assert plateau["beats_bh_sharpe"].mean() == 1.0

    snap = json.loads((OUT_DIR / "gold_live_snapshot_2026_11_20.json").read_text(encoding="utf-8"))
    assert snap["as_of"] == "2026-11-20"
    assert {"GLD", "518880", "PAXG"}.issubset(snap.keys())
