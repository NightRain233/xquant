# Theme Alpha Q8: Signal Stability and Near-Live Rules Review

Date: 2026-06-23

## Research Question

Q8 asks whether the current Theme Alpha candidate still works after moving from a research-friendly rebalance rule to a more realistic execution framework:

- change 10 trading-day rebalance to fixed twice-monthly calendar signals;
- use close signal and trade on the next trading day;
- add ETF liquidity, spread, and premium/discount friction assumptions;
- keep the Q7 practical controls: 2% minimum rebalance threshold and 15% max single-ETF trade per rebalance.

The main candidate entering Q8 was:

- `Core80 / Expanded LVT20 / Def200 Cash / 10D`

The main Q8 question is whether that should remain a 10D strategy, or whether it can become a fixed twice-monthly near-live process.

## Setup

### Portfolio Candidates

| Candidate | Meaning |
|---|---|
| `Base_Core80_LVT20` | 80% three-asset core plus 20% expanded LVT satellite, without core defensive rule |
| `Def200_Cash` | Same structure, but core risk-off uses 200-day defense and moves defensive sleeve to cash |
| `Def210_Gold` | Same structure, but defensive sleeve uses gold instead of cash |

### Rebalance Schedules

| Schedule | Rule |
|---|---|
| `10D` | Every 10 trading days, anchored from the first sample trading day |
| `BIMONTHLY` | Fixed calendar dates on the 10th and 25th, shifted to the next available trading day |
| `M` | Monthly last trading day, used as a lower-frequency reference |

### Execution and Friction

The preferred near-live assumption is:

- signal is computed with closing data;
- trade is executed on the next trading day;
- asset-level trading friction is added on top of base 20 bps one-way cost.

Friction assumptions:

| Mode | Assumption |
|---|---|
| `base20` | 20 bps one-way transaction cost |
| `base20_plus_asset` | 20 bps plus asset-specific spread/premium-discount allowance |
| `base20_plus_asset_stress` | Same as above, but the asset-specific component is doubled |

Asset-specific extra friction uses a simple conservative ladder:

- broad domestic / gold ETF: +5 bps;
- domestic sector/theme ETF: +10 bps;
- cross-border / QDII / Hong Kong tech ETF: +20 bps.

## Main Result: Near-Live Assumption

The table below uses the stricter Q8 default:

`next_close + base20_plus_asset`

| Window | Candidate | Schedule | Return | Max DD | Sharpe | Calmar | Days <= -10% DD | Annual Cost Drag | Avg Cash |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021_to_date | Base_Core80_LVT20 | 10D | 106.01% | -14.22% | 1.23 | 1.04 | 87 | 1.68% | 0.08% |
| 2021_to_date | Base_Core80_LVT20 | BIMONTHLY | 101.32% | -16.41% | 1.19 | 0.87 | 139 | 1.71% | 0.27% |
| 2021_to_date | Def200_Cash | 10D | 94.30% | -11.41% | 1.28 | 1.18 | 1 | 1.73% | 16.07% |
| 2021_to_date | Def200_Cash | BIMONTHLY | 110.04% | -11.29% | 1.40 | 1.34 | 1 | 1.72% | 16.22% |
| 2021_to_date | Def210_Gold | 10D | 117.04% | -11.81% | 1.34 | 1.35 | 2 | 1.76% | 0.83% |
| 2021_to_date | Def210_Gold | BIMONTHLY | 138.09% | -11.29% | 1.48 | 1.59 | 1 | 1.74% | 0.56% |
| 2022_full | Base_Core80_LVT20 | 10D | -7.20% | -10.93% | -0.65 | -0.69 | 4 | 1.64% | 0.00% |
| 2022_full | Base_Core80_LVT20 | BIMONTHLY | -10.11% | -13.94% | -0.92 | -0.75 | 51 | 1.67% | 0.00% |
| 2022_full | Def200_Cash | 10D | 0.90% | -4.59% | 0.14 | 0.20 | 0 | 1.36% | 38.90% |
| 2022_full | Def200_Cash | BIMONTHLY | -1.20% | -5.04% | -0.19 | -0.25 | 0 | 1.34% | 38.85% |
| 2022_full | Def210_Gold | 10D | 4.46% | -7.02% | 0.43 | 0.66 | 0 | 1.23% | 0.72% |
| 2022_full | Def210_Gold | BIMONTHLY | 2.36% | -8.61% | 0.22 | 0.29 | 0 | 1.20% | 0.42% |
| 2025_to_date | Base_Core80_LVT20 | 10D | 45.40% | -11.81% | 1.97 | 2.59 | 2 | 1.82% | 0.19% |
| 2025_to_date | Base_Core80_LVT20 | BIMONTHLY | 44.99% | -11.29% | 1.92 | 2.68 | 2 | 1.70% | 0.10% |
| 2025_to_date | Def200_Cash | 10D | 40.84% | -11.41% | 1.88 | 2.42 | 1 | 2.00% | 2.78% |
| 2025_to_date | Def200_Cash | BIMONTHLY | 41.83% | -11.29% | 1.81 | 2.50 | 1 | 1.82% | 1.43% |
| 2026_ytd | Base_Core80_LVT20 | 10D | 6.72% | -11.81% | 0.81 | 1.35 | 2 | 1.77% | 0.00% |
| 2026_ytd | Base_Core80_LVT20 | BIMONTHLY | 7.53% | -11.29% | 0.89 | 1.59 | 2 | 1.33% | 0.00% |
| 2026_ytd | Def200_Cash | 10D | 4.54% | -11.41% | 0.57 | 0.93 | 1 | 2.11% | 3.18% |
| 2026_ytd | Def200_Cash | BIMONTHLY | 6.67% | -11.29% | 0.80 | 1.40 | 1 | 1.55% | 1.49% |

## Interpretation

### 1. Fixed twice-monthly does not break the strategy

The most important Q8 finding is that fixed twice-monthly signals are not obviously worse than 10D.

For the base strategy, `BIMONTHLY` is weaker over the long window: return falls from 106.01% to 101.32%, max drawdown widens from -14.22% to -16.41%, and time below -10% drawdown increases.

But once the core defensive rule is added, the twice-monthly schedule becomes competitive:

- `Def200_Cash` improves from 94.30% to 110.04% over 2021-to-date;
- max drawdown stays almost unchanged, around -11.3%;
- days below -10% drawdown stay at only 1 day;
- 2025-to-date and 2026-to-date are also slightly better under `BIMONTHLY`.

This does not mean "the 10th and 25th are magic dates." It means the strategy is not fragile to leaving the artificial 10-trading-day clock. That is a good sign for moving toward a real operating rule.

### 2. The cash defense still matters

The base strategy has higher exposure but weaker drawdown behavior:

- 2022 full year: base `10D` returned -7.20%, while `Def200_Cash 10D` returned +0.90%;
- 2022 full year: base `BIMONTHLY` returned -10.11%, while `Def200_Cash BIMONTHLY` returned -1.20%;
- 2021-to-date: base `BIMONTHLY` had 139 days below -10% drawdown, while `Def200_Cash BIMONTHLY` had only 1.

So Q8 confirms the Q6/Q7 conclusion: the LVT satellite is useful, but the portfolio also needs a core-level defense rule. Low-vol trend rotation alone is not a full bear-market solution.

### 3. `Def210_Gold` is still the return leader, but not the cleanest defensive rule

`Def210_Gold BIMONTHLY` is the historical winner in the Q8 table:

- 2021-to-date return: 138.09%;
- max drawdown: -11.29%;
- Sharpe: 1.48;
- Calmar: 1.59.

However, this relies on gold remaining a useful defensive and return asset. That may be true in some regimes, but it is not as clean as cash. Cash defense says, "when core risk is bad, reduce risk." Gold defense says, "when core risk is bad, rotate into another risk asset that historically helped."

For future research, `Def210_Gold` is the aggressive return candidate. `Def200_Cash` remains the more structurally conservative candidate.

### 4. Next-day execution and asset friction lower returns, but do not erase the edge

With `base20_plus_asset`, annualized cost drag is around 1.7% for the main candidates. That is meaningful.

This tells us two things:

- the strategy is not a free lunch; turnover and ETF trading frictions matter;
- the candidate survives a more conservative cost model, especially after the defensive rule is added.

The cost drag is high enough that future work should avoid making the strategy more hyperactive. The current 2% rebalance threshold and 15% max trade cap should stay.

## Liquidity Check

Liquidity was tested with portfolio AUM assumptions of 1 million, 10 million, and 50 million CNY. The metric is max single-trade participation as a percentage of 20-day average traded value.

Worst assets by AUM:

| AUM | Main Bottleneck | Max ADV20 Participation | Comment |
|---:|---|---:|---|
| 1 million | Energy ETF `159930.SZ` | 1.29% | Operationally acceptable |
| 10 million | Energy ETF `159930.SZ` | 12.86% | Mostly okay, but a few stress trades are too large |
| 50 million | Energy ETF `159930.SZ` | 64.28% | Not acceptable without liquidity constraints |

At 10 million CNY, most ETFs are manageable:

- dividend ETF max participation: 3.30%;
- Nasdaq ETF: 2.96%;
- communication ETF: 1.99%;
- healthcare ETF: 0.96%;
- nonferrous ETF: 0.66%.

The main issue is `159930.SZ` energy ETF. It is not always selected, but when selected or removed, it can create concentrated liquidity pressure. For a small account this is fine. For larger accounts, the strategy needs one of:

- an energy ETF cap;
- a liquidity-adjusted position cap;
- a minimum ADV filter;
- execution split over several days;
- replacement with a more liquid energy/oil-related ETF if available.

## Current Target Weights

Latest `BIMONTHLY` target weights for the conservative candidate:

| Asset | Weight |
|---|---:|
| 沪深300ETF | 35.38% |
| 纳指100ETF | 25.48% |
| 黄金ETF | 27.81% |
| 芯片ETF | 5.55% |
| 通信ETF | 5.78% |
| 现金 | 0.00% |

The core defense is not active in the latest state, so `Def200_Cash` currently has no cash allocation. This is expected: the cash sleeve only appears when the core defensive condition is triggered.

## Conclusion Template

- Historical best: `Def210_Gold BIMONTHLY`, because it has the highest 2021-to-date return, Sharpe, and Calmar under the Q8 near-live assumptions.
- Risk-adjusted best: also `Def210_Gold BIMONTHLY` historically, but it depends on gold as an active defensive asset.
- Most structurally balanced: `Def200_Cash BIMONTHLY`, because it keeps drawdown control, survives next-day execution and ETF friction, and is easier to explain as a defensive rule.
- Main sample-period advantage: gold performed well as a diversifier/defensive asset, and the 10th/25th calendar may have benefited from this particular sample path.
- Main future failure mode: a broad risk-off market where theme ETFs gap down before the next signal, or a liquidity event where selected satellite ETFs become expensive to enter/exit.
- What to test next: calendar-date sensitivity and liquidity-aware constraints.

## Recommendation

The practical candidate should be updated from:

`Core80 / Expanded LVT20 / Def200 Cash / 10D`

to:

`Core80 / Expanded LVT20 / Def200 Cash / fixed twice-monthly / close-signal-next-day-trade / asset-friction`

This is not because twice-monthly is guaranteed to be better than 10D. It is because it is much easier to operate, less tied to an arbitrary trading-day anchor, and still performs well after realistic execution assumptions.

The aggressive research candidate remains:

`Core80 / Expanded LVT20 / Def210 Gold / fixed twice-monthly / close-signal-next-day-trade / asset-friction`

But it should not replace the cash-defense candidate until gold-defense robustness is tested across more regimes.

## Files

- Notebook: `theme-alpha-q8-signal-live-readiness-practice.ipynb`
- Plan: `docs/plans/2026-06-23-theme-alpha-q8-signal-live-readiness.md`
- Outputs: `outputs/theme-alpha-q8-signal-live-readiness/`
- Main summary: `outputs/theme-alpha-q8-signal-live-readiness/research_summary.csv`
- Liquidity summary: `outputs/theme-alpha-q8-signal-live-readiness/liquidity_participation_summary.csv`
- NAV charts:
  - `outputs/theme-alpha-q8-signal-live-readiness/nav_q8_selected_2021_to_date.png`
  - `outputs/theme-alpha-q8-signal-live-readiness/nav_q8_selected_2022_full.png`
  - `outputs/theme-alpha-q8-signal-live-readiness/nav_q8_selected_2025_to_date.png`
- Underwater charts:
  - `outputs/theme-alpha-q8-signal-live-readiness/underwater_q8_selected_2021_to_date.png`
  - `outputs/theme-alpha-q8-signal-live-readiness/underwater_q8_selected_2022_full.png`
  - `outputs/theme-alpha-q8-signal-live-readiness/underwater_q8_selected_2025_to_date.png`

