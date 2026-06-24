# Theme Alpha Q8 Signal Live Readiness Plan

Date: 2026-06-23

## Purpose

Q8 tests signal stability and near-live execution rules for the current Theme Alpha candidates.

The main questions are:

1. Can the 10-trading-day schedule be replaced by fixed twice-monthly calendar signal dates?
2. Does close-signal / next-trading-day execution materially change the result?
3. Do liquidity, estimated spread, and premium/discount assumptions threaten the strategy?

## Candidates

Primary candidate:

- Core80 / Expanded LVT20 Def200 Cash

Comparison candidates:

- Core80 / Expanded LVT20
- Core80 / Expanded LVT20 Def210 Gold

## Signal Schedules

Compare:

- Rolling 10 trading days from the 2020-01-02 anchor
- Fixed twice-monthly calendar schedule: 10th and 25th calendar day, shifted to the next available trading day
- Monthly schedule as a slower reference

## Execution Timing

Compare:

- Same-close proxy: target generated on signal close and portfolio return starts next trading day
- Next-trading-day execution: signal generated on signal close; trade occurs at next trading day's close; new weights start earning the following trading day

The second rule is the preferred near-live assumption.

## Friction Assumptions

Use two layers:

1. Fixed one-way base cost:
   - 20 bps

2. Asset-level extra friction assumptions:
   - broad domestic ETF: 5 bps
   - gold ETF: 5 bps
   - domestic sector/theme ETF: 10 bps
   - cross-border/QDII/HK tech ETF: 20 bps

Stress case:

- double the asset-level extra friction.

## Liquidity Checks

Use yfinance volume and close price to estimate daily turnover:

- daily value traded = close * volume
- 20-day ADV and 60-day ADV

Test AUM assumptions:

- 1 million CNY
- 10 million CNY
- 50 million CNY

Report:

- max single-trade participation as % of 20-day ADV
- average trade participation
- number of trades above 5% and 10% of ADV

## Windows

- 2021-to-date
- 2021-2022 bear
- 2022 full
- 2025-to-date
- 2026 YTD

## Outputs

Save under:

- `outputs/theme-alpha-q8-signal-live-readiness/`

Required files:

- `data_availability.csv`
- `signal_schedule_comparison.csv`
- `execution_timing_comparison.csv`
- `friction_stress_comparison.csv`
- `liquidity_participation_summary.csv`
- `latest_target_weights.csv`
- selected NAV and underwater charts

## Interpretation Rules

A candidate is closer to live readiness only if:

- fixed twice-monthly schedule remains close to 10D;
- next-day execution does not destroy the edge;
- friction stress does not erase the strategy's bear-market value;
- 10 million CNY AUM does not require large participation in normal ETF volume.

If the strategy depends too much on exact 10D timing, mark it as timing-sensitive rather than production-ready.
