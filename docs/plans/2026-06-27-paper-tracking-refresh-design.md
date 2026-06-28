# Paper Tracking Refresh and Sleeve Attribution Design

## Goal

Refresh both dashboard paper-tracking strategies through the 2026-06-26 close and make the Theme Alpha LVT20 sleeve fully attributable.

## Date Semantics

Theme Alpha uses three different dates:

- Market data date: 2026-06-26, the latest close included in the refreshed research outputs.
- Signal date: 2026-06-25, the scheduled twice-monthly signal date.
- Execution date: 2026-06-26, the next trading day used by the paper-tracking rule.

BTC SuperTrend uses the latest common ETF trading date, so its latest signal date and market data date are both 2026-06-26.

The Q12 benchmark conclusion remains a static research snapshot. Its date must stay visible in the conclusion instead of being presented as the paper-tracking signal date.

## Data Flow

The existing practice notebooks remain the source of strategy calculations:

- `research/notebooks/theme-alpha-q8-signal-live-readiness-practice.ipynb`
- `research/notebooks/q10-live-readiness-stress-practice.ipynb`

The Theme Alpha notebook will additionally export:

- `latest_sleeve_weights.csv`, containing Core and LVT internal target weights plus sleeve allocations.
- `paper_tracking_snapshot.csv`, containing market-data, signal, and execution dates.

The dashboard builder will consume these files directly. It will not infer LVT ownership by subtracting aggregate weights because Nasdaq and gold can belong to both Core and LVT.

## Dashboard Presentation

Keep the existing aggregate target-weight table because it is the actionable whole-portfolio target.

Below it, render an `LVT20 袖层拆解` table with:

- Asset name.
- LVT internal target weight, summing to 100%.
- Whole-portfolio contribution, summing to 20%.

Add a short explanation that overlapping assets such as Nasdaq are consolidated into one column in the aggregate table.

The signal panel will explicitly show market-data date, signal date, and execution date where applicable.

## Refresh Scope

- Re-execute Q8 Theme Alpha and Q10 BTC practice notebooks against current market data.
- Rebuild the dashboard static strategy packages.
- Do not change strategy parameters, asset pools, weighting rules, or research conclusions.
- Do not refresh Q12 robustness research merely to change the paper-tracking signal.

## Testing

- Builder tests assert the three Theme Alpha dates and that LVT internal weights sum to 100% while portfolio contributions sum to 20%.
- Component tests assert that the sleeve table and overlap explanation render.
- Existing BTC and Theme Alpha builder tests continue to protect prior data contracts.
- Final verification runs the Python tests relevant to exported research structure plus `make dashboard-check`.
