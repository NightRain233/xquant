"""Old-vs-new comparison tables, data manifest and self-check file for the corrected-price BTC satellite rerun."""
import hashlib, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/btc-satellite-corrected-prices-2026-10-18'
OLD = ROOT / 'outputs/strategy-healthcheck-clock-correction-2026-10-03/btc'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

new = pd.read_csv(OUT / 'summary.csv'); old = pd.read_csv(OLD / 'summary.csv')
S = ['BTC_0', 'BTC_5', 'BTC_7.5', 'BTC_10']
metrics = ['cagr', 'max_drawdown', 'annualized_volatility', 'longest_underwater_sessions', 'return', 'sharpe_zero_rf']
rows = []
for per in ['full_common', '2026_ytd', 'recent_3m']:
    for s in S:
        o = old[(old.strategy == s) & (old.period == per)].iloc[0]; n = new[(new.strategy == s) & (new.period == per)].iloc[0]
        r = {'strategy': s, 'period': per}
        for m in metrics: r[f'old_{m}'] = o[m]; r[f'new_{m}'] = n[m]; r[f'diff_{m}'] = n[m] - o[m]
        rows.append(r)
cmp = pd.DataFrame(rows); cmp.to_csv(OUT / 'old_vs_new.csv', index=False)

ro = pd.read_csv(OLD / 'rolling_3y_5y.csv'); rn = pd.read_csv(OUT / 'rolling_3y_5y.csv')
roll = rn.merge(ro[['strategy', 'years', 'worst_total_return']].rename(columns={'worst_total_return': 'old_worst_total_return'}), on=['strategy', 'years'])
roll = roll.rename(columns={'worst_total_return': 'new_worst_total_return'}); roll['diff'] = roll.new_worst_total_return - roll.old_worst_total_return
roll.to_csv(OUT / 'rolling_old_vs_new.csv', index=False)

ao = pd.read_csv(OLD / 'annual_returns.csv'); an = pd.read_csv(OUT / 'annual_returns.csv')
ann = an.merge(ao[['strategy', 'year', 'return']].rename(columns={'return': 'old_return'}), on=['strategy', 'year']).rename(columns={'return': 'new_return'})
ann['diff'] = ann.new_return - ann.old_return; ann.to_csv(OUT / 'annual_old_vs_new.csv', index=False)

# BTC increment vs BTC_0
inc = []
for tag, df, p in [('old', old, 'full_common'), ('new', new, 'full_common')]:
    b0 = df[(df.strategy == 'BTC_0') & (df.period == p)].iloc[0]
    for s in S[1:]:
        x = df[(df.strategy == s) & (df.period == p)].iloc[0]
        inc.append({'basis': tag, 'strategy': s, 'cagr_minus_BTC_0': x.cagr - b0.cagr, 'maxdd_minus_BTC_0': x.max_drawdown - b0.max_drawdown,
                    'vol_minus_BTC_0': x.annualized_volatility - b0.annualized_volatility, 'return_minus_BTC_0': x['return'] - b0['return']})
pd.DataFrame(inc).to_csv(OUT / 'btc_increment.csv', index=False)
a = an.pivot(index='year', columns='strategy', values='return')
yr = pd.DataFrame({'BTC_7.5_minus_BTC_0': a['BTC_7.5'] - a['BTC_0']}); yr['years_positive'] = yr.iloc[:, 0] > 0
yr.to_csv(OUT / 'btc_increment_by_year.csv')

# manifest
files = {}
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name not in ('data_manifest.json', 'README.md'): files[p.name] = sha(p)
for p in sorted((OUT / 'inputs').iterdir()): files['inputs/' + p.name] = sha(p)
for p in sorted((OUT / 'market_data').iterdir()): files['market_data/' + p.name] = sha(p)
dm = {'core_price_source': 'TickFlow free API /v1/klines/batch adjust=forward (proportional forward adjustment, dividends reinvested; total-return)',
      'fetch_script': 'scripts/fetch_weinstein_etf_data.py (fetch function reused, symbols 510300/513100/518880, 2013-01-01 to 2026-10-02 exclusive, truncated to 2026-09-30)',
      'raw_none_reference': 'inputs/tickflow_none_510300_513100_518880.json (unadjusted, fetched alongside, audit only)',
      'independent_reference': 'outputs/etf-dividend-valuation-2026-10-04 raw.json + corporate_actions.csv (raw price + verified dividends/split)',
      'raw_json_sha256': sha(ROOT / 'outputs/etf-dividend-valuation-2026-10-04/inputs/raw.json'),
      'corporate_actions_sha256': sha(ROOT / 'outputs/etf-dividend-valuation-2026-10-04/corporate_actions.csv'),
      'btc_source': 'outputs/strategy-healthcheck-2026-10-02/market_data/BTC-USD.parquet (frozen, copied unchanged)',
      'btc_sha256_original': sha(ROOT / 'outputs/strategy-healthcheck-2026-10-02/market_data/BTC-USD.parquet'),
      'old_core_snapshot_sha256': {s: sha(ROOT / f'outputs/strategy-healthcheck-2026-10-02/market_data/{s}.parquet') for s in ['510300.SS', '513100.SS', '518880.SS']},
      'window': '2013-01-04 to 2026-09-30 (ETF); backtest 2016-06-07 to 2026-09-30', 'files_sha256': files}
(OUT / 'data_manifest.json').write_text(json.dumps(dm, ensure_ascii=False, indent=2) + '\n')

part = json.loads((OUT / 'self_checks_partial.json').read_text())
cons = pd.read_csv(OUT / 'price_consistency.csv')
ref = cons[cons.versus == 'rawdiv_reference']
part['price_consistency_vs_raw_plus_dividends'] = ref.to_dict('records')
part['core_price_equals_old_for_513100_518880'] = bool(cons[(cons.versus == 'additive_old') & cons.symbol.isin(['513100.SS', '518880.SS'])].max_abs_diff_bp.max() < 20)
part['btc_data_unchanged'] = sha(OUT / 'market_data/BTC-USD.parquet') == dm['btc_sha256_original']
part['all_pass'] = bool(part['btc_data_unchanged'] and all(v['max_cash_error'] < 1e-6 and v['max_abs_weight_sum_minus_1'] < 1e-9 and v['fills_not_after_signal_available'] == 0
                        and v['fills_using_future_price'] == 0 and v['negative_cash_rows'] == 0 for v in part['strategies'].values())
                        and all(r['max_rel_nav_diff'] < 1e-9 for r in part['harness_reproduction']))
(OUT / 'self_checks.json').write_text(json.dumps(part, ensure_ascii=False, indent=2, default=str) + '\n')
(OUT / 'self_checks_partial.json').unlink()
print(part['all_pass'])
