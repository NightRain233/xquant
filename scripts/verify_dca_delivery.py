"""Independently rebuild cash/holdings/units, then reproduce the portable study.

Does not import the cash-flow replay or its summary functions for the audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import exchange_calendars as xcals
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/dca-comparison-2026-10-04"


def independent_ledger(manifest):
    paths={Path(name).name:Path(name) if Path(name).is_absolute() else ROOT/name for name in manifest["inputs"]}
    frames={s:pd.read_parquet(paths[s+".parquet"]) for s in ["510300.SS","513100.SS","518880.SS","SPY","CNY=X"]}
    audit=pd.read_csv(OUT/"valuation_quotes.csv",parse_dates=["date","valuation_at","spy_close_label","spy_close_available_at","fx_label","fx_available_at"])
    funding=pd.read_csv(OUT/"contribution_clock.csv",parse_dates=["release_at","spy_execution_at","spy_bar_label","fx_label_used","fx_available_at"])
    cal=xcals.get_calendar("XNYS",start="2013-01-01",end="2026-10-02")
    assert (funding.release_at<funding.spy_execution_at).all()
    assert (funding.fx_available_at<funding.spy_execution_at).all()
    assert (audit.spy_close_available_at<audit.valuation_at).all()
    assert (audit.fx_available_at<audit.valuation_at).all()
    for day,stamp in zip(funding.spy_bar_label,funding.spy_execution_at):
        assert cal.session_open(day)==stamp
    expected_close=pd.DatetimeIndex(cal.schedule.loc[audit.spy_close_label,"close"])+pd.Timedelta(seconds=1)
    assert np.array_equal(expected_close.as_unit("ns").asi8,pd.DatetimeIndex(audit.spy_close_available_at).as_unit("ns").asi8)
    fx=frames["CNY=X"]
    fx_times=(fx.index.tz_localize("UTC")+pd.Timedelta(days=1,seconds=1)).as_unit("ns").asi8
    fx_positions=np.searchsorted(fx_times,pd.DatetimeIndex(audit.valuation_at).as_unit("ns").asi8,side="right")-1
    assert np.array_equal(fx.index[fx_positions],pd.DatetimeIndex(audit.fx_label))
    fx_values=fx.Close.to_numpy(float)[fx_positions]
    expected_mark=frames["SPY"].loc[audit.spy_close_label,"Close"].to_numpy(float)*fx_values
    np.testing.assert_allclose(expected_mark,audit.spy_quote_cny,rtol=1e-13,atol=1e-9)
    assert audit.spy_close_label.iloc[-1]==pd.Timestamp("2026-09-29")
    assert audit.valuation_at.iloc[-1]==pd.Timestamp("2026-09-30 07:00:02",tz="UTC")
    results={};shared_flows=None
    for strategy in ["Three","Two","SP500"]:
        daily=pd.read_csv(OUT/f"account_{strategy}.csv",index_col=0,parse_dates=True)
        fills=pd.read_csv(OUT/f"fills_{strategy}.csv")
        if shared_flows is None:shared_flows=daily.contribution
        else:pd.testing.assert_series_equal(shared_flows,daily.contribution)
        assert int((daily.contribution>0).sum())==141
        assert daily.contribution.sum()==1410000
        assert np.isclose(daily.principal.iloc[-1],daily.contribution.sum())
        core=["510300.SS","513100.SS","518880.SS"]
        close=np.column_stack([frames[s].Close.reindex(frames[s].index.union(daily.index)).ffill().reindex(daily.index).to_numpy(float) for s in core])
        opening=np.column_stack([frames[s].Open.reindex(daily.index).to_numpy(float) for s in core])
        grouped={int(i):group for i,group in fills.groupby("valuation_index")}
        q=np.zeros(1 if strategy=="SP500" else 3)
        cash=units=0.0
        maximum_nav_error=maximum_unit_error=maximum_fee_error=maximum_pnl_error=maximum_exit_error=0.0
        previous_mark=np.array([expected_mark[0]]) if strategy=="SP500" else close[0]
        for i,(day,row) in enumerate(daily.iterrows()):
            mark=np.array([expected_mark[i]]) if strategy=="SP500" else close[i]
            pnl=float(q@(mark-previous_mark))
            group=grouped.get(i)
            if strategy!="SP500" and row.contribution>0:
                before=float(cash+q@opening[i]);price=before/units if units else 1.0
                assert np.isclose(price,row.pre_flow_unit_price,rtol=1e-10)
                units+=row.contribution/price;cash+=row.contribution
            cost=0.0
            if group is not None:
                for fill in group.itertuples():
                    symbol=0 if strategy=="SP500" else int(fill.symbol_index)
                    if strategy=="SP500":
                        j=int(fill.funding_month_index)
                        clock=funding.iloc[j]
                        px=float(frames["SPY"].loc[clock.spy_bar_label,"Open"]*frames["CNY=X"].loc[clock.fx_label_used,"Close"])
                        assert np.isclose(px,fill.execution_price_cny,rtol=1e-12)
                        assert cash+1e-7>=fill.gross_notional_cny+fill.cost_cny
                    else:
                        px=float(opening[i,symbol])
                        assert np.isclose(px,fill.execution_price_cny,rtol=1e-12)
                    notional=abs(fill.quantity_delta*px)
                    maximum_fee_error=max(maximum_fee_error,abs(fill.cost_cny-notional*.001))
                    q[symbol]+=fill.quantity_delta
                    cash-=fill.quantity_delta*px+fill.cost_cny
                    pnl+=fill.quantity_delta*(mark[symbol]-px)
                    cost+=fill.cost_cny
            if strategy=="SP500" and row.contribution>0:
                before=float(cash+q@mark);price=before/units if units else 1.0
                assert np.isclose(price,row.pre_flow_unit_price,rtol=1e-10)
                units+=row.contribution/price;cash+=row.contribution
            assert cash>=-1e-6 and (q>=-1e-8).all()
            wealth=float(cash+q@mark)
            liquidation=float(cash+(q@mark)*.999)
            maximum_nav_error=max(maximum_nav_error,abs(wealth-row.wealth))
            maximum_unit_error=max(maximum_unit_error,abs(wealth/units-row.unit_nav))
            maximum_pnl_error=max(maximum_pnl_error,abs(pnl-row.market_pnl))
            maximum_exit_error=max(maximum_exit_error,abs(liquidation-row.liquidation_wealth))
            assert abs(cost-row.cost)<1e-5
            previous_mark=mark
        assert maximum_nav_error<1e-5 and maximum_unit_error<1e-8
        assert maximum_fee_error<1e-5 and maximum_pnl_error<1e-5 and maximum_exit_error<1e-5
        results[strategy]={"nav_max_error":maximum_nav_error,"unit_max_error":maximum_unit_error,
                           "fee_max_error":maximum_fee_error,"pnl_max_error":maximum_pnl_error,
                           "hypothetical_exit_max_error":maximum_exit_error,"fill_rows":len(fills),
                           "principal":float(daily.principal.iloc[-1]),"terminal_profit":float(daily.profit.iloc[-1])}
    return {"accounts":results,"funding_rows":len(funding),"valuation_rows":len(audit),
            "causal_clock_checks":"passed; FX vendor bar cutoff remains unverified assumption"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-only",action="store_true")
    args=parser.parse_args()
    manifest=json.loads((OUT/"manifest.json").read_text())
    hashes=0
    for group in ["inputs","source","outputs","reports"]:
        for name,expected in manifest[group].items():
            path=Path(name) if group=="inputs" and Path(name).is_absolute() else (OUT/name if group=="outputs" else ROOT/name)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,name
            hashes+=1
    with zipfile.ZipFile(OUT/"reproduction_bundle.zip") as bundle:
        for name,expected in manifest["bundle_members"].items():
            assert hashlib.sha256(bundle.read(name)).hexdigest()==expected,name
    ledger=independent_ledger(manifest)
    env={**os.environ,"PYTHONPATH":str(ROOT/"src")}
    test_command=[sys.executable,"-m","pytest","tests/test_cashflow_research.py","-q"]
    tested=subprocess.run(test_command,cwd=ROOT,env=env,text=True,capture_output=True)
    assert tested.returncode==0,tested.stdout+tested.stderr
    test_evidence={"returncode":tested.returncode,"stdout":tested.stdout,"stderr":tested.stderr,"command":test_command}
    (OUT/"test_results.json").write_text(json.dumps(test_evidence,indent=2))
    reproduction={"status":"not_requested","csvs_compared":0}
    if not args.ledger_only:
        with tempfile.TemporaryDirectory(prefix="dca-standalone-") as temporary:
            work=Path(temporary)
            with zipfile.ZipFile(OUT/"reproduction_bundle.zip") as bundle:bundle.extractall(work)
            command=[sys.executable,"scripts/review_dca_accounts.py","--snapshot","inputs/market_data","--reference","inputs/reference","--workers","2"]
            computed=subprocess.run(command,cwd=work,text=True,capture_output=True)
            assert computed.returncode==0,computed.stdout+computed.stderr
            rendered=subprocess.run([sys.executable,"scripts/render_dca_review.py"],cwd=work,text=True,capture_output=True)
            assert rendered.returncode==0,rendered.stdout+rendered.stderr
            count=0
            for original in OUT.glob("*.csv"):
                fresh=work/"outputs/dca-comparison-2026-10-04"/original.name
                pd.testing.assert_frame_equal(pd.read_csv(original),pd.read_csv(fresh),rtol=1e-12,atol=1e-8)
                count+=1
            reproduction={"status":"passed","csvs_compared":count,"command":command,
                          "stdout":computed.stdout,"stderr":computed.stderr}
    result={"status":"passed","hashes_checked":hashes,"independent_main_ledgers":ledger,
            "tests":test_evidence,"standalone_reproduction":reproduction,
            "scope":"Independent fill replay covers three main accounts; all 813 cohort ledgers validate conservation at run time."}
    evidence_path=OUT/"delivery_verification.json"
    evidence_path.write_text(json.dumps(result,indent=2))
    for path in [evidence_path,OUT/"test_results.json"]:
        manifest["outputs"][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps({"status":result["status"],"hashes_checked":hashes,
                      "independent_ledger":ledger,"csvs_compared":reproduction["csvs_compared"]},indent=2))


if __name__=="__main__":main()
