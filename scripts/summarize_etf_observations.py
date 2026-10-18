"""Offline monitor coverage and optional-gate counts, never a performance test."""
import argparse
from collections import Counter
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"outputs/etf-dividend-valuation-2026-10-04/monitor")
    args=parser.parse_args();out=args.output
    rows=[json.loads(line) for line in (out/"observations.jsonl").read_text().splitlines()]
    result=[]
    for symbol in sorted({r["symbol"] for r in rows}):
        group=[r for r in rows if r["symbol"]==symbol]
        eligible_samples=[r for r in group if r["counts_as_prospective_trading_day"]]
        caps=sorted({r["cap"] for r in group if r["cap"] is not None})
        variants=[]
        for cap in caps:
            checked=[r for r in eligible_samples if r["cap"]==cap]
            paused=[r for r in checked if r["optional_gate_eligible"] is False]
            variants.append({"cap":cap,"valid_quote_samples":len(checked),"paused_samples":len(paused),
                             "pause_share":len(paused)/len(checked) if checked else None,
                             "pause_reasons":dict(Counter(reason for r in paused for reason in r["diagnostic_reasons"])),
                             "warning":"intraday snapshots are correlated; not independent trading-day estimates"})
        result.append({"symbol":symbol,"all_real_collection_samples":len(group),
                       "samples_with_nav":sum(r.get("nav") is not None for r in group),
                       "nav_publication_timestamp_verified_samples":sum(r.get("nav_published_at") is not None for r in group),
                       "samples_with_verified_current_interval":sum(r.get("fair_value_lower") is not None and not set(r["diagnostic_reasons"]).intersection({"current_valuation_interval_unverified","future_reference","stale_reference","future_underlying_or_fx","invalid_interval","invalid_reference_clock_or_value"}) for r in group),
                       "valid_session_quote_samples":len(eligible_samples),"optional_variants":variants,
                       "all_sample_diagnostic_reasons":dict(Counter(reason for r in group for reason in r["diagnostic_reasons"]))})
    (out/"coverage_summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=="__main__":main()
