# Open-sizing lookahead audit fix

This experiment preserves the frozen signal, universe, SuperTrend, MA200,
cost, concurrency, and sleeve-budget parameters from
`scan-v2-all-bull-flip-defense`. It changes only the price used to mark
existing positions when sizing a new order at the execution-day Open:

- previous implementation: execution-day Close;
- corrected implementation: execution-day Open, falling back to the latest
  completed Close when that symbol has no valid Open on the date.

The original frozen output directory is intentionally unchanged.

## Metric impact versus the frozen baseline

| Strategy | CAGR change | Sharpe change | Max drawdown change |
|---|---:|---:|---:|
| bull_flip_baseline | -0.0590 pp | -0.0025 | +0.0001 pp |
| bull_flip_def200_entry_gate | -0.0297 pp | -0.0014 | -0.1222 pp |
| risk_parity_core | 0.0000 pp | 0.0000 | 0.0000 pp |
| core90_bull10 | -0.0059 pp | -0.0005 | +0.0040 pp |
| core90_def200_bull10 | -0.0027 pp | -0.0002 | +0.0009 pp |
| core80_bull20 | -0.0117 pp | -0.0010 | +0.0084 pp |
| core70_bull30 | -0.0176 pp | -0.0014 | +0.0089 pp |

The correction does not change the qualitative strategy ranking or the
conclusion that the MA200 entry gate mainly improves the loss path. The old
metrics remain a frozen historical artifact; use this directory for the
lookahead-safe comparison.
