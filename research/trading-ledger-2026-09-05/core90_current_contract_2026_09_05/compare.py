"""Compare execution entry orders and normalized NAV across recorded versions."""
import argparse
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current',type=Path,required=True)
    parser.add_argument('--before',type=Path,default=ROOT/'before_2_0')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    legacy=ROOT.parent/'core90_recovery_2026_09_05/verified_legacy'
    old_orders=pd.read_csv(legacy/'bull_flip_def200_entry_gate_orders.csv')
    old=old_orders[old_orders.side.eq('buy')&old_orders.status.eq('executed')][['symbol','date','executionPrice']].rename(columns={'executionPrice':'legacy_price'})
    new_orders=pd.read_csv(args.current/'orders.csv')
    entries=new_orders[new_orders.order_type.eq('BULL_FLIP_ENTRY')&new_orders.status.eq('EXECUTED')]
    fills=pd.read_csv(args.current/'fills.csv')
    new=entries[['id','symbol','signal_date','actual_execution_date']].merge(fills[['order_id','execution_price']],left_on='id',right_on='order_id')
    new=new.rename(columns={'actual_execution_date':'date','execution_price':'current_price'})
    entry_diff=old.merge(new[['symbol','date','signal_date','current_price']],on=['symbol','date'],how='outer',indicator=True)
    entry_diff.to_csv(args.output/'legacy_vs_current_entry_orders.csv',index=False)
    before=pd.read_csv(args.before/'daily_nav.csv')[['valuation_date','net_nav']].rename(columns={'net_nav':'before_nav'})
    current=pd.read_csv(args.current/'daily_nav.csv')[['valuation_date','net_nav']].rename(columns={'net_nav':'current_nav'})
    nav=before.merge(current,on='valuation_date',how='outer',indicator=True)
    nav['difference']=nav.current_nav-nav.before_nav
    nav.to_csv(args.output/'before_vs_after_daily_nav.csv',index=False)
    rows=[]
    for label,path,key in [('legacy',legacy/'metrics.json','core90_def200_bull10'),
                           ('before_2_0',args.before/'metrics.json',None),('repaired_2_1',args.current/'metrics.json',None)]:
        report=json.loads(path.read_text());values=report['metrics'][key] if key else report['metrics']
        rows.append({'version':label,**{k:values[k] for k in ['cagr','sharpe','maxDrawdown']}})
    pd.DataFrame(rows).to_csv(args.output/'metrics_comparison.csv',index=False)
    summary={'entryOrderComparison':{str(k):int(v) for k,v in entry_diff['_merge'].value_counts().items()},
        'entryMatchKey':'symbol + actual execution date; no inferred signal-date matching',
        'scope':'Legacy entries are standalone MA200 satellite trades; current entries are portfolio-budgeted satellite trades. Resize orders excluded.',
        'currentEntryCount':len(entries),'legacyEntryCount':len(old),'metrics':rows}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
