"""Recompute the current Core90 contract from archived prices, without legacy signals."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

import numpy as np
import pandas as pd

PACKAGE_DIR = Path(__file__).resolve().parent
RESEARCH_ROOT = PACKAGE_DIR.parent
XQUANT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRADING_ROOT = XQUANT_ROOT.parent / 'trading'


def source_inventory(trading_root: Path):
    """Return source files and stable archive names for both repositories."""
    trading_files = sorted((trading_root / 'backend/portfolio_strategies').glob('*.py'))
    trading_files += [
        trading_root / 'backend/portfolio_strategies/fixtures/xquant_frozen_v1.json',
        trading_root / 'backend/uv.lock',
    ]
    xquant_files = [PACKAGE_DIR / 'recompute.py', RESEARCH_ROOT / 'core90_recovery_2026_09_05/reproduce.py']
    entries = [(path, f'trading/{path.relative_to(trading_root).as_posix()}') for path in trading_files]
    entries += [(path, f'xquant/{path.relative_to(XQUANT_ROOT).as_posix()}') for path in xquant_files]
    return entries


def metrics(nav):
    nav=nav.sort_values('valuation_date')
    value=nav.net_nav.astype(float)
    returns=value.pct_change().fillna(0.)
    years=max(1,(pd.Timestamp(nav.valuation_date.iloc[-1])-pd.Timestamp(nav.valuation_date.iloc[0])).days)/365.25
    annualization=len(returns)/years
    deviation=returns.std(ddof=1)
    drawdown=value/value.cummax()-1
    return {'startNav':float(value.iloc[0]),'endNav':float(value.iloc[-1]),
        'cagr':float((value.iloc[-1]/value.iloc[0])**(1/years)-1),
        'sharpe':float(returns.mean()/deviation*np.sqrt(annualization)) if deviation>0 else None,
        'maxDrawdown':float(drawdown.min()),'calendarRows':len(nav)}


def audit_quantities(conn):
    positions=pd.read_sql_query("SELECT valuation_date,sleeve,symbol,quantity FROM portfolio_positions_v2 WHERE authoritative=1 AND symbol!='CASH'",conn)
    fills=pd.read_sql_query('SELECT e.actual_execution_date AS valuation_date,o.sleeve,o.symbol,e.quantity_delta FROM paper_executions e JOIN paper_orders o ON o.id=e.order_id',conn)
    rows=[]
    for (sleeve,symbol),group in positions.groupby(['sleeve','symbol']):
        selected=fills[(fills.sleeve==sleeve)&(fills.symbol==symbol)]
        changes=selected.groupby('valuation_date').quantity_delta.sum().sort_index().cumsum()
        for row in group.itertuples():
            known=changes.loc[:row.valuation_date]
            expected=float(known.iloc[-1]) if len(known) else 0.
            difference=float(row.quantity)-expected
            if not np.isclose(row.quantity,expected,rtol=1e-9,atol=1e-7):
                rows.append({'date':row.valuation_date,'sleeve':sleeve,'symbol':symbol,
                             'ledgerQuantity':float(row.quantity),'quantityFromFills':expected,'difference':difference})
    return pd.DataFrame(rows,columns=['date','sleeve','symbol','ledgerQuantity','quantityFromFills','difference'])


def audit_cash_and_timing(conn, initial_nav):
    cash=pd.read_sql_query("SELECT valuation_date,SUM(quantity) AS cash FROM portfolio_positions_v2 WHERE authoritative=1 AND symbol='CASH' GROUP BY valuation_date",conn)
    flows=pd.read_sql_query('SELECT actual_execution_date AS valuation_date,SUM(-quantity_delta*execution_price-commission) AS flow FROM paper_executions GROUP BY actual_execution_date ORDER BY actual_execution_date',conn)
    flow=flows.set_index('valuation_date').flow.cumsum() if len(flows) else pd.Series(dtype=float)
    rows=[]
    for row in cash.itertuples():
        known=flow.loc[:row.valuation_date]
        expected=initial_nav+(float(known.iloc[-1]) if len(known) else 0.)
        rows.append({'date':row.valuation_date,'ledgerCash':row.cash,'cashFromFills':expected,'difference':row.cash-expected})
    cash_audit=pd.DataFrame(rows)
    invalid_timing=conn.execute('SELECT COUNT(*) FROM paper_executions WHERE actual_execution_date<=signal_date').fetchone()[0]
    return cash_audit,int(invalid_timing)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--start',default='2015-01-01')
    parser.add_argument('--end',default='2026-07-10')
    parser.add_argument('--trading-root',type=Path,
        default=Path(__import__('os').environ.get('TRADING_ROOT', DEFAULT_TRADING_ROOT)))
    args=parser.parse_args()
    trading_root=args.trading_root.resolve()
    sys.path.insert(0,str(trading_root/'backend'))
    from portfolio_strategies.core_bull_research import run_current_contract
    from portfolio_strategies.registry import get_strategy
    original=RESEARCH_ROOT/'core90_recovery_2026_09_05'
    spec=importlib.util.spec_from_file_location('recovery',original/'reproduce.py')
    recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)
    source=recovery.verify_archive(original)
    args.output.mkdir(parents=True,exist_ok=False)
    config=get_strategy('core90_ma200_bull10')
    sources=source_inventory(trading_root)
    hashes={archive_name:hashlib.sha256(path.read_bytes()).hexdigest() for path,archive_name in sources}
    manifest={'strategyId':config.strategy_id,'strategyVersion':config.version,'params':dict(config.params),
        'initialNav':config.initial_nav,'baseCurrency':config.base_currency,'assets':[asdict(a) for a in config.assets],
        'sourceArchiveSha256':source['archiveSha256'],'sourceHashes':hashes,
        'baseGitCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=trading_root,text=True).strip(),
        'start':args.start,'end':args.end,'activation':'cash on calendar day before start',
        'universeScope':'limited_observable_universe','signalInput':'raw OHLCV; legacy events and trades are NOT used',
        'fxPolicy':'current contract: foreign-currency entries blocked; CNY listed proxies allowed',
        'executionStatusCoverage':'positive finite Open only when opening-status feed absent',
        'calendarConvention':'daily bar labels; all same-date reference closes known by following 00:00 UTC before CNY next open'}
    with zipfile.ZipFile(args.output/'source_bundle.zip','w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for file,archive_name in sources:bundle.write(file,archive_name)
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    with tempfile.TemporaryDirectory(prefix='core90-current-input-') as temp:
        source_dir=Path(temp)
        with zipfile.ZipFile(original/'original_xquant.zip') as bundle:
            names=[n for n in bundle.namelist() if n.startswith('outputs/scan-v2-all-bull-flip-long-sample/market_data/') and n.endswith('.parquet') and not n.endswith('_weekly.parquet')]
            for name in names: bundle.extract(name,source_dir)
        prices={Path(n).stem:pd.read_parquet(source_dir/n)[['Open','High','Low','Close','Volume']] for n in names}
        run_current_contract(config,prices,start=date.fromisoformat(args.start),end=date.fromisoformat(args.end),
            db_path=args.output/'research.sqlite',progress=lambda event: print(json.dumps(event),flush=True))
    with sqlite3.connect(args.output/'research.sqlite') as conn:
        tables={'decisions':'decision_runs','decision_items':'decision_items','orders':'paper_orders','fills':'paper_executions',
            'positions':'portfolio_positions_v2','daily_nav':'portfolio_nav_v2','universe':'universe_snapshots',
            'memberships':'universe_memberships','sleeve_transfers':'sleeve_transfer_events','attempts':'paper_order_attempts','checkpoints':'next_open_session_checkpoints'}
        for name,table in tables.items():
            where=' WHERE authoritative=1' if name in {'positions','daily_nav','decisions'} else ''
            order='session_date' if name=='checkpoints' else 'id'
            frame=pd.read_sql_query(f'SELECT * FROM {table}{where} ORDER BY {order}',conn)
            frame.drop(columns=[c for c in ['created_at','updated_at','observed_at'] if c in frame],inplace=True)
            frame.to_csv(args.output/f'{name}.csv',index=False)
        audit=audit_quantities(conn);audit.to_csv(args.output/'quantity_reconciliation.csv',index=False)
        nav=pd.read_sql_query('SELECT * FROM portfolio_nav_v2 WHERE authoritative=1 ORDER BY valuation_date',conn)
        cash_audit,invalid_timing=audit_cash_and_timing(conn,config.initial_nav)
        cash_audit.to_csv(args.output/'cash_reconciliation.csv',index=False)
        passed=audit.empty and cash_audit.difference.abs().max()<1e-6 and invalid_timing==0
        result={'status':'PASS_EXECUTION_AUDIT' if passed else 'FAIL_EXECUTION_AUDIT',
                'maxCashDifference':float(cash_audit.difference.abs().max()),'invalidTimingFills':invalid_timing,
                'quantityMismatchRows':len(audit),'metrics':metrics(nav[nav.valuation_date>=args.start]),
                'historicalValidationScope':'current contract on limited observable universe',
                'validated':bool(passed),
                'notValidated':['full historical security master','FX-enabled foreign instruments','complete historical opening restrictions','out-of-sample profitability'],
                'decisionItems':pd.read_sql_query('SELECT event_type,eligible,reason,COUNT(*) AS count FROM decision_items GROUP BY event_type,eligible,reason',conn).to_dict('records')}
        (args.output/'metrics.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    old=pd.read_csv(original/'verified_legacy/core90_def200_bull10_daily_nav.csv',parse_dates=['date'])
    old=old[['date','nav']].rename(columns={'nav':'legacy_nav'})
    old['legacy_nav']/=1_000_000.
    current=nav[['valuation_date','net_nav']].rename(columns={'valuation_date':'date','net_nav':'current_nav'})
    current['date']=pd.to_datetime(current['date']);current['current_nav']/=config.initial_nav
    old.merge(current,on='date',how='inner').to_csv(args.output/'legacy_vs_current_nav.csv',index=False)
    print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
