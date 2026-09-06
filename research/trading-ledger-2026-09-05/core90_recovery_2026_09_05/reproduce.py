"""Offline recovery audit. Run with trading/backend's locked Python environment.

Replays archived xquant code and inputs; does NOT claim parity with the current
paper contract. Writes exclusively into a new output directory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LONG = 'outputs/scan-v2-all-bull-flip-long-sample'
FIXED = 'outputs/scan-v2-all-bull-flip-defense-open-sizing-fix-2026-08-20'


def verify_archive(root: Path = ROOT) -> dict:
    manifest = json.loads((root / 'source_manifest.json').read_text())
    archive = root / 'original_xquant.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['archiveSha256']:
        raise ValueError('Archive SHA256 mismatch')
    with zipfile.ZipFile(archive) as bundle:
        expected = {row['path'] for row in manifest['files']}
        if set(bundle.namelist()) != expected:
            raise ValueError('Archive inventory mismatch')
        for row in manifest['files']:
            path = Path(row['path'])
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive path')
            data = bundle.read(row['path'])
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError(f"Source mismatch: {path}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = verify_archive()
    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='xquant-recovered-') as temporary:
        source = Path(temporary)
        with zipfile.ZipFile(ROOT / 'original_xquant.zip') as bundle:
            bundle.extractall(source)
        sys.path.insert(0, str(source / 'src'))
        from xquant.defensive_overlay import (
            CorePortfolioConfig, align_nav_to_calendar, combine_core_satellite,
            filter_entries_by_market_ma, run_inverse_volatility_core,
        )
        from xquant.point_in_time_universe import filter_entries_by_membership
        from xquant.signal_portfolio import (
            PortfolioConfig, decision_entries, performance_metrics, run_signal_portfolio,
        )
        symbols = json.loads((source / 'research/universes/scan-v2-long-sample-candidates.json').read_text())['symbols']
        prices = {s: pd.read_parquet(source / LONG / 'market_data' / f'{s}.parquet') for s in symbols}
        inventory = [{'symbol': s, 'rows': len(f), 'firstDate': str(f.index.min()),
                      'lastDate': str(f.index.max())} for s, f in prices.items()]
        pd.DataFrame(inventory).to_csv(args.output / 'universe_manifest.csv', index=False)
        membership = pd.read_csv(source / LONG / 'universe_membership_history.csv')
        membership = membership[membership['universe'].eq('rolling_monthly_pit')]
        decisions = pd.read_parquet(source / LONG / 'policy_bull_flip_events.parquet')
        decisions['market'] = decisions['symbol'].map(membership.groupby('symbol')['market'].last())
        entries = filter_entries_by_membership(decision_entries(decisions, 'all_bull_flip'), membership)
        references = {'a_share': '510300.SS', 'hong_kong': '2800.HK', 'us': 'SPY', 'crypto': 'BTC-USD', 'gold': 'GC=F'}
        gated, audit = filter_entries_by_market_ma(entries, prices, references, window=200)
        audit.to_csv(args.output / 'decisions_ma200.csv', index=False)
        results = {}
        for name, signals in [('bull_flip_baseline', entries), ('bull_flip_def200_entry_gate', gated)]:
            results[name] = run_signal_portfolio(signals, prices, start='2015-01-01', end='2026-07-10', config=PortfolioConfig())
            for key in ('orders', 'trades'):
                results[name][key].to_csv(args.output / f'{name}_{key}.csv', index=False)
        core = run_inverse_volatility_core(prices, ('510300.SS', '513100.SS', '518880.SS'), start='2015-01-01', end='2026-07-10', config=CorePortfolioConfig())
        core_nav = align_nav_to_calendar(core['nav'], pd.DatetimeIndex(results['bull_flip_baseline']['nav']['date']))
        combined = combine_core_satellite(core_nav, results['bull_flip_def200_entry_gate']['nav'], core_weight=0.9,
            rebalance_dates=pd.DatetimeIndex(core['nav']['date'].iloc[::10]), initial_capital=1_000_000.0, sleeve_rebalance_cost_bps=10.0)
        results['core90_def200_bull10'] = combined
        recorded = pd.read_csv(source / FIXED / 'nav_daily.csv', parse_dates=['date'])
        metrics, differences = {}, []
        for name, result in results.items():
            nav = result['nav'].copy()
            nav.to_csv(args.output / f'{name}_daily_nav.csv', index=False)
            metrics[name] = performance_metrics(nav, result.get('trades'))
            actual = nav[['date','nav']].copy(); actual['date'] = pd.to_datetime(actual['date'])
            expected = recorded[recorded['strategy'].eq(name)][['date','nav']]
            joined = expected.merge(actual, on='date', how='outer', suffixes=('_recorded','_replayed'), indicator=True)
            joined['difference'] = joined['nav_replayed'] - joined['nav_recorded']
            joined['strategy'] = name
            differences.append(joined)
        diff = pd.concat(differences, ignore_index=True)
        diff.to_csv(args.output / 'recorded_vs_replayed_nav.csv', index=False)
        matched = bool(diff['_merge'].eq('both').all() and np.allclose(diff['nav_recorded'], diff['nav_replayed'], rtol=1e-10, atol=1e-6))
        # JSON null instead of non-standard NaN for unavailable statistics.
        clean_metrics = {name: {k: None if pd.isna(v) else v for k,v in values.items()} for name,values in metrics.items()}
        report = {'status': 'LEGACY_REPRODUCED' if matched else 'LEGACY_DIVERGENCE',
                  'currentContractValidated': False, 'universeScope': 'limited_observable_universe',
                  'sourceGitHead': manifest['sourceGitHead'], 'archiveSha256': manifest['archiveSha256'],
                  'priceFileCount': len(prices), 'maxAbsoluteNavDifference': float(diff['difference'].abs().max()),
                  'metrics': clean_metrics}
        (args.output / 'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='metrics'}, indent=2))
        if not matched:
            raise SystemExit('Recorded NAV and recovered-source replay differ; inspect the difference artifact.')


if __name__ == '__main__':
    main()
