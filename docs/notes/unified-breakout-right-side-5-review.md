# Unified breakout right-side 5 review

## Decision

Replace the legacy post-flip SuperTrend distance gate with an executable next-session price boundary:

- formal trigger: completed `bull_flip` close;
- maximum next-session price: trigger plus `0.5 ATR`;
- invalidation anchor: SuperTrend value fixed at the formal signal close;
- extra close-time gate: MACD histogram must be positive;
- market mode, weekly trend, and ADX gates remain unchanged.

The production policy version is `scan_v2_right_side_5`.

## Why the legacy gate was removed

The old rule measured the close against the newly generated bullish SuperTrend line. Across 47 watchlist symbols from 2023-03-01 through 2026-07-10, there were 368 daily bull-flip candidates but no formal breakout buys. Median distance to that new line was 3.33 ATR and only one candidate was within 2 ATR. The gate was therefore structurally mismatched to the state transition, not merely conservative.

## Point-in-time validation

The new stream contains the same 37,262 decisions and changes only the breakout branch. It produces 36 formal breakout signals; 33 were executable at the next open and three opened above the 0.5 ATR maximum. With 20 bps round-trip costs, the 33 independent executed events returned on average 0.40%, 1.02%, and 1.81% over 5, 10, and 20 sessions; the 20-session median was 0.87% and hit rate 57.6%.

Pullback and compression counts are unchanged, confirming that the modification is isolated to breakout decisions.

## Limitations

This remains a cross-asset heuristic with a small breakout sample, uneven calendar coverage, and no untouched out-of-sample segment. The result fixes reachability and gives a positive first validation; it does not establish portfolio-level capacity or statistical certainty. Continue paper tracking and re-evaluate after more signals accumulate.

## Reproduce

Generate the `scan_v2_right_side_5` decision stream with the trading repository's `scripts/replay_unified_decisions.py`, then run:

```bash
uv run python scripts/research_unified_scan_policy_events.py \
  --decisions outputs/unified-scan-policy-v2-breakout-r5/decision_stream.parquet \
  --decision-metadata outputs/unified-scan-policy-v2-breakout-r5/decision_stream.metadata.json \
  --price-data-dir ../trading/backend/data \
  --output-dir outputs/unified-scan-policy-v2-breakout-r5

uv run python scripts/research_breakout_policy_ablation.py \
  --decisions outputs/unified-scan-policy-v2/decision_stream.parquet \
  --price-data-dir ../trading/backend/data \
  --output outputs/unified-scan-policy-v2-breakout-r5/breakout_ablation.csv
```
