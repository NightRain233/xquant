"""Replay core-only variants through the repaired next-open paper ledger."""
from datetime import date
from pathlib import Path
from dataclasses import replace
import importlib.util
import os
import json, sqlite3, tempfile, zipfile, sys
import pandas as pd

PACKAGE_DIR=Path(__file__).resolve().parent
RESEARCH_ROOT=PACKAGE_DIR.parent
XQUANT_ROOT=Path(__file__).resolve().parents[3]
DEFAULT_TRADING_ROOT=XQUANT_ROOT.parent/'trading'

def metric(db):
    with sqlite3.connect(db) as c:
        n=pd.read_sql_query("select valuation_date,net_nav from portfolio_nav_v2 where authoritative=1 order by valuation_date",c)
    n=n[n.valuation_date>='2015-01-01']; v=n.net_nav.astype(float); r=v.pct_change().fillna(0)
    years=(pd.Timestamp(n.valuation_date.iloc[-1])-pd.Timestamp(n.valuation_date.iloc[0])).days/365.25
    return {'startNav':float(v.iloc[0]),'endNav':float(v.iloc[-1]),'cagr':float((v.iloc[-1]/v.iloc[0])**(1/years)-1),'sharpe':float(r.mean()/r.std(ddof=1)*(len(r)/years)**.5),'maxDrawdown':float((v/v.cummax()-1).min()),'rows':len(v)}

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('variants',nargs='*')
    parser.add_argument('--trading-root',type=Path,default=Path(os.environ.get('TRADING_ROOT',DEFAULT_TRADING_ROOT)))
    args=parser.parse_args()
    out=args.output; out.mkdir(parents=True,exist_ok=False)
    trading_root=args.trading_root.resolve()
    sys.path.insert(0,str(trading_root/'backend'))
    from portfolio_strategies.core_bull_research import run_current_contract
    from portfolio_strategies.registry import get_strategy
    audit_spec=importlib.util.spec_from_file_location(
        'current_recompute', RESEARCH_ROOT/'core90_current_contract_2026_09_05/recompute.py')
    audit_module=importlib.util.module_from_spec(audit_spec); audit_spec.loader.exec_module(audit_module)
    archive=RESEARCH_ROOT/'core90_recovery_2026_09_05/original_xquant.zip'
    with tempfile.TemporaryDirectory() as t:
        td=Path(t)
        with zipfile.ZipFile(archive) as z:
            names=[n for n in z.namelist() if n.startswith('outputs/scan-v2-all-bull-flip-long-sample/market_data/') and n.endswith('.parquet') and not n.endswith('_weekly.parquet')]
            for n in names:z.extract(n,td)
        prices={Path(n).stem:pd.read_parquet(td/n)[['Open','High','Low','Close','Volume']] for n in names}
        rp=get_strategy('risk_parity_core_next_open')
        st=replace(rp, strategy_id='risk_parity_core_supertrend_filter', version='1.0.0',
            display_name='RiskParity with core SuperTrend filter',
            params={**rp.params, 'core_supertrend_atr_window':10, 'core_supertrend_multiplier':3.0})
        delayed=replace(rp, strategy_id='risk_parity_core_next_open_delay1', version='1.0.0',
            display_name='RiskParity next-open plus one-session delay',
            params={**rp.params, 'execution_delay_sessions':1})
        configs=[
            ('pure_risk_parity',rp,False,False,0),
            ('core90_cash',get_strategy('core90_ma200_bull10'),False,False,0),
            ('core_supertrend_filter',st,False,True,0),
            ('pure_risk_parity_delay1',delayed,False,False,1),
            ('core90_ma200_bull10_repaired',get_strategy('core90_ma200_bull10'),True,False,0),
        ]
        requested=set(args.variants)
        if requested:
            configs=[item for item in configs if item[0] in requested]
        result=[]
        audits=[]
        for label,cfg,bull,core_filter,delay in configs:
            db=out/(label+'.sqlite'); run_current_contract(cfg,prices,start=date(2015,1,1),end=date(2026,7,10),db_path=db,include_bull=bull,core_supertrend_filter=core_filter,execution_delay_sessions=delay)
            result.append({'variant':label,**metric(db)})
            ledger_dir=out/'repaired_ledgers'/label; ledger_dir.mkdir(parents=True)
            with sqlite3.connect(db) as conn:
                tables={'decisions':'decision_runs','decision_items':'decision_items','orders':'paper_orders',
                        'fills':'paper_executions','positions':'portfolio_positions_v2',
                        'daily_nav':'portfolio_nav_v2','checkpoints':'next_open_session_checkpoints'}
                for name,table in tables.items():
                    where=' WHERE authoritative=1' if name in {'decisions','positions','daily_nav'} else ''
                    order='session_date' if name=='checkpoints' else 'id'
                    frame=pd.read_sql_query(f'SELECT * FROM {table}{where} ORDER BY {order}',conn)
                    frame.drop(columns=[c for c in ['created_at','updated_at','observed_at'] if c in frame],inplace=True)
                    frame.to_csv(ledger_dir/f'{name}.csv',index=False)
                quantity=audit_module.audit_quantities(conn)
                cash,invalid=audit_module.audit_cash_and_timing(conn,cfg.initial_nav)
            quantity.to_csv(ledger_dir/'quantity_reconciliation.csv',index=False)
            cash.to_csv(ledger_dir/'cash_reconciliation.csv',index=False)
            audit={'variant':label,'quantityMismatchRows':len(quantity),
                   'maxCashDifference':float(cash.difference.abs().max()),
                   'invalidTimingFills':invalid,
                   'passed':bool(quantity.empty and cash.difference.abs().max()<1e-6 and invalid==0)}
            (out/'repaired_ledgers'/f'audit_{label}.json').write_text(json.dumps(audit,indent=2)+'\n')
            audits.append(audit)
    (out/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'repaired_ledger_metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'repaired_ledger_comparison.csv').write_text(pd.DataFrame(result).to_csv(index=False))
    (out/'repaired_ledgers').mkdir(exist_ok=True)
    (out/'repaired_ledgers/audit.json').write_text(json.dumps(audits,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
