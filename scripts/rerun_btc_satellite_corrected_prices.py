"""Rerun the clock-corrected BTC satellite study with corrected core ETF prices.

Only the three core ETF price series change (TickFlow proportional forward
adjustment = total-return). BTC data, parameters, clocks and costs are frozen
exactly as in strategy-healthcheck-clock-correction-2026-10-03.
Run with the trading backend venv (needs portfolio_strategies, exchange_calendars).
"""
import hashlib, json, shutil, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import review_cross_market_clock as clock
prior = clock.prior

SLUG = 'btc-satellite-corrected-prices-2026-10-18'
OUT = ROOT / 'outputs' / SLUG
OLD_SNAP = ROOT / 'outputs/strategy-healthcheck-2026-10-02/market_data'
OLD_RUN = ROOT / 'outputs/strategy-healthcheck-clock-correction-2026-10-03/btc'
DIV = ROOT / 'outputs/etf-dividend-valuation-2026-10-04'
CORE = ['510300.SS', '513100.SS', '518880.SS']
END = pd.Timestamp('2026-09-30')


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(path, key_fmt):
    data = json.loads(Path(path).read_text())['data']
    frames = {}
    for sym in CORE:
        v = data[sym.replace('.SS', '.SH')]
        idx = pd.to_datetime(v['timestamp'], unit='ms', utc=True).tz_convert('Asia/Shanghai').tz_localize(None).normalize()
        f = pd.DataFrame({'Open': v['open'], 'High': v['high'], 'Low': v['low'], 'Close': v['close'],
                          'Volume': np.asarray(v['volume'], dtype='int64')}, index=pd.DatetimeIndex(idx).as_unit('ms'))
        frames[sym] = f.loc[:END]
    return frames


def raw_div_returns():
    """Independent reference: raw close + verified cash dividends reinvested at ex-date close; 513100 split handled."""
    raw = parse_raw()
    acts = pd.read_csv(DIV / 'corporate_actions.csv', parse_dates=['effective_quote_date'])
    out = {}
    for sym in CORE:
        c = raw[sym].Close
        code = sym.split('.')[0]
        r = c.pct_change()
        for a in acts[acts.symbol.astype(str) == code].itertuples():
            d = a.effective_quote_date
            if d not in c.index: continue
            prev = c.index[c.index.get_loc(d) - 1]
            if a.action_type == 'cash_dividend':
                r.loc[d] = (c.loc[d] + a.cash_per_share) / c.loc[prev] - 1
            elif a.action_type == 'split':
                r.loc[d] = c.loc[d] * a.split_ratio / c.loc[prev] - 1
        out[sym] = r.dropna()
    return out


def parse_raw():
    data = json.loads((DIV / 'inputs/raw.json').read_text())['data']
    res = {}
    for sym in CORE:
        v = data[sym.replace('.SS', '.SH')]
        idx = pd.to_datetime(v['timestamp'], unit='ms', utc=True).tz_convert('Asia/Shanghai').tz_localize(None).normalize()
        res[sym] = pd.DataFrame({'Close': v['close']}, index=idx).loc[:END]
    return res


def metrics_extra(nav):
    s = nav.nav
    ret = s.pct_change().dropna()
    return {'ann_vol': float(ret.std(ddof=1) * np.sqrt(252))}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'market_data').mkdir(exist_ok=True)
    fwd = parse(OUT / 'inputs/tickflow_forward_510300_513100_518880.json', None)
    for s, f in fwd.items(): f.to_parquet(OUT / 'market_data' / f'{s}.parquet')
    shutil.copy(OLD_SNAP / 'BTC-USD.parquet', OUT / 'market_data/BTC-USD.parquet')
    snap = OUT / 'market_data'

    # ---- return consistency checks
    ref = raw_div_returns()
    rows = []; worst = []
    for s in CORE:
        old = pd.read_parquet(OLD_SNAP / f'{s}.parquet').Close
        new_r = fwd[s].Close.pct_change().dropna(); old_r = old.pct_change().dropna(); r_ref = ref[s]
        for name, other in [('additive_old', old_r), ('rawdiv_reference', r_ref)]:
            j = pd.concat([new_r, other], axis=1, join='inner').dropna(); j.columns = ['new', 'other']
            d = (j.new - j.other).abs()
            rows.append({'symbol': s, 'versus': name, 'common_days': len(j), 'mean_abs_diff_bp': d.mean() * 1e4,
                         'p99_abs_diff_bp': d.quantile(.99) * 1e4, 'max_abs_diff_bp': d.max() * 1e4,
                         'max_diff_date': str(d.idxmax().date()), 'days_over_5bp': int((d > 5e-4).sum()),
                         'days_over_50bp': int((d > 5e-3).sum()),
                         'total_return_new': float((1 + j.new).prod() - 1), 'total_return_other': float((1 + j.other).prod() - 1),
                         'ann_vol_new': float(j.new.std() * np.sqrt(252)), 'ann_vol_other': float(j.other.std() * np.sqrt(252)),
                         'days_missing_in_other': int(len(new_r) - len(j))})
            if name == 'additive_old':
                for dt, v in d.nlargest(3).items(): worst.append({'symbol': s, 'date': str(dt.date()), 'new_ret': j.new[dt], 'additive_ret': j.other[dt], 'diff_pp': v * 100})
    cons = pd.DataFrame(rows); cons.to_csv(OUT / 'price_consistency.csv', index=False)
    pd.DataFrame(worst).to_csv(OUT / 'price_additive_vs_corrected_top_diffs.csv', index=False)

    # ---- harness reproduction: old data must reproduce saved old NAV
    config = prior.get_strategy('btc_supertrend_satellite')
    asof = datetime(2026, 10, 2, 16, tzinfo=ZoneInfo('Asia/Shanghai'))

    def run(snapshot, tag, save=None):
        market = prior.load_market(config, snapshot, asof, '2016-05-01')
        targets, obs = prior.btc_targets(config, market)
        frames = {s: pd.read_parquet(snapshot / f'{s}.parquet').loc['2016-05-01':] for s in config.symbols}
        res = {}
        for label in ('BTC_0', 'BTC_5', 'BTC_7.5', 'BTC_10'):
            nav, events, audit = clock.btc_replay(config, market, frames, targets[label])
            res[label] = (nav, events, audit); print(tag, label, flush=True)
        return market, targets, obs, res

    mk_old, t_old, _, r_old = run(OLD_SNAP, 'repro')
    repro = []
    for label, (nav, _, _) in r_old.items():
        saved = pd.read_csv(OLD_RUN / f'nav_{label}.csv', index_col=0, parse_dates=True).nav
        j = pd.concat([nav.nav, saved], axis=1, join='inner'); j.columns = ['rerun', 'saved']
        repro.append({'strategy': label, 'rows_rerun': len(nav), 'rows_saved': len(saved),
                      'max_rel_nav_diff': float(((j.rerun - j.saved).abs() / j.saved).max())})
    pd.DataFrame(repro).to_csv(OUT / 'harness_reproduction.csv', index=False)

    market, targets, obs, res = run(snap, 'corrected')
    prior.dump(OUT / 'signals_corrected.json', obs)
    # target weight shift
    tw = []
    for label in ('BTC_0',):
        for day, tgt in targets[label].items():
            o = t_old[label].get(day)
            if o: tw.append({'signal_date': str(day.date()), **{f'new_{k}': tgt[k] for k in CORE}, **{f'old_{k}': o[k] for k in CORE}})
    twd = pd.DataFrame(tw)
    for k in CORE: twd[f'diff_{k}'] = twd[f'new_{k}'] - twd[f'old_{k}']
    twd.to_csv(OUT / 'core_target_weights_old_vs_new.csv', index=False)

    # ---- outputs per strategy
    windows = {'full_common': '2016-06-07', '2026_ytd': '2025-12-31', 'recent_3m': '2026-06-30'}
    summ = []; annual = []; rolling = []; selfchk = {'strategies': {}}
    for label, (nav, events, audit) in res.items():
        nav.to_csv(OUT / f'nav_{label}.csv'); prior.dump(OUT / f'fills_{label}.json', audit)
        for p, st in windows.items(): summ.append({'strategy': label, 'period': p, **prior.summarize(nav, st, market.sessions[-1])})
        rets = nav.nav.pct_change().fillna(0)
        for y, v in rets.groupby(rets.index.year):
            annual.append({'strategy': label, 'year': y, 'return': float((1 + v).prod() - 1), 'partial_year': y in [nav.index[0].year, nav.index[-1].year]})
        s = nav.nav
        for yrs in (3, 5):
            ends = s.index[s.index >= s.index[0] + pd.DateOffset(years=yrs)]
            pos = s.index.searchsorted(ends - pd.DateOffset(years=yrs), side='right') - 1
            vals = s.loc[ends].to_numpy() / s.iloc[pos].to_numpy() - 1
            rolling.append({'strategy': label, 'years': yrs, 'windows': len(ends), 'worst_total_return': float(vals.min()),
                            'worst_end_date': str(ends[int(vals.argmin())].date())})
        # self checks: cash+holdings = NAV; fills after signals
        wsum = (nav.filter(like='weight_').sum(axis=1) + nav.cash_weight - 1).abs().max()
        cash_err = max((r['cashError'] for r in audit), default=0.)
        sig = {e['signal_date']: pd.Timestamp(e['signal_available_at']) for e in events}
        viol = sum(int(pd.Timestamp(r['executionAt']) <= sig[r['signal_date']]) for r in audit)
        late_price = sum(int(any(pd.Timestamp(t) > pd.Timestamp(r['executionAt']) for t in r['pricesKnownAt'].values())) for r in audit)
        selfchk['strategies'][label] = {'max_abs_weight_sum_minus_1': float(wsum), 'max_cash_error': float(cash_err), 'trade_groups': len(audit),
                                        'fills_not_after_signal_available': viol, 'fills_using_future_price': late_price, 'nav_min': float(s.min()), 'negative_cash_rows': int((nav.cash_weight < -1e-9).sum())}
    # explicit fill time vs signal time check
    pd.DataFrame(summ).to_csv(OUT / 'summary.csv', index=False)
    pd.DataFrame(annual).to_csv(OUT / 'annual_returns.csv', index=False)
    pd.DataFrame(rolling).to_csv(OUT / 'rolling_3y_5y.csv', index=False)
    selfchk['harness_reproduction'] = repro
    selfchk['sessions'] = [str(market.sessions[0].date()), str(market.sessions[-1].date())]
    prior.dump(OUT / 'self_checks_partial.json', selfchk)


if __name__ == '__main__':
    main()
