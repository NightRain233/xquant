"""One-shot append-only public-data collection. Research only, never orders.

No scheduler is installed. First-seen times are actual HTTP completion clocks,
not NAV valuation dates or claimed publisher times. Raw errors are retained.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from xquant.etf_valuation_monitor import CN, CALENDAR_SOURCE, assess_observation

SLUG="etf-dividend-valuation-2026-10-04"


def utc_now():return datetime.now(timezone.utc)


def fetch(url, folder, name, encoding="utf-8"):
    started=utc_now()
    record={"url":url,"request_started_at":started.isoformat(),"status":"error"}
    try:
        referer="https://fundf10.eastmoney.com/" if "api.fund.eastmoney.com" in url else "https://finance.sina.com.cn/"
        request=Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":referer})
        with urlopen(request,timeout=12) as response:
            payload=response.read()
            record["http_status"]=response.status
        (folder/(name+".raw")).write_bytes(payload)
        record.update(status="ok",sha256=hashlib.sha256(payload).hexdigest(),raw_path=name+".raw")
        content=payload.decode(encoding,errors="replace")
    except Exception as exc:
        record["error_type"]=type(exc).__name__
        record["error"]=str(exc)[:300]
        content=None
    record["first_seen_at"]=utc_now().isoformat()
    (folder/(name+".fetch.json")).write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
    return content,record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"outputs"/SLUG/"monitor")
    parser.add_argument("--symbols",nargs="+",default=["513100","513300","513500","159655","159612"])
    parser.add_argument("--premium-cap",type=float,default=None,help="Optional paper diagnostic only; no default threshold")
    parser.add_argument("--references",type=Path,help="Researcher supplied current interval evidence JSON; never last-NAV alone")
    parser.add_argument("--paper-budgets",type=Path,help="Snapshot of hypothetical per-symbol intended buys; no funds or trades")
    parser.add_argument("--paper-plan-id",help="Stable hypothetical plan id for waiting-duration records; never a trade instruction")
    args=parser.parse_args()
    if any(not re.fullmatch(r"\d{6}",s) for s in args.symbols):parser.error("six-digit codes required")
    if args.premium_cap is not None and not 0 <= args.premium_cap <= 1:parser.error("cap must be a fraction between 0 and 1")
    if args.paper_budgets and (args.premium_cap is None or not args.paper_plan_id):
        parser.error("paper budgets require an explicit cap and stable paper-plan-id")
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    # An exclusive directory lock protects first-seen and append operations.
    lock=out/".collection.lock"
    try:lock.mkdir()
    except FileExistsError:raise SystemExit("Collection lock exists; check another run or interrupted process")
    try:
        run_id=utc_now().strftime("%Y%m%dT%H%M%S.%fZ")+"-"+uuid.uuid4().hex[:8]
        folder=out/"raw"/run_id;folder.mkdir(parents=True)
        references=json.loads(args.references.read_text()) if args.references else {}
        budgets=json.loads(args.paper_budgets.read_text()) if args.paper_budgets else {}
        for label,path in [("references",args.references),("paper_budgets",args.paper_budgets)]:
            if path:(folder/(label+".input.json")).write_bytes(path.read_bytes())
        state_path=out/"first_seen_state.json"
        state=json.loads(state_path.read_text()) if state_path.exists() else {"started_at":utc_now().isoformat(),"nav":{}}
        symbols=[("sh" if s.startswith("5") else "sz")+s for s in args.symbols]
        quote_url="https://hq.sinajs.cn/list="+",".join(symbols)
        content,quote_fetch=fetch(quote_url,folder,"quotes","gb18030")
        quotes={}
        if content:
            for line in content.splitlines():
                match=re.search(r"(?:sh|sz)(\d{6})=\"([^\"]*)\"",line)
                if match:quotes[match[1]]=match[2].split(",")
        rows=[]
        for s in args.symbols:
            q=quotes.get(s,[])
            row={"run_id":run_id,"symbol":s,"quote_fetch":quote_fetch,"quote_at":None,
                 "quote_first_seen_at":quote_fetch["first_seen_at"],"bid":None,"ask":None,
                 "nav":None,"nav_date":None,"nav_published_at":None,"iopv":None,
                 "iopv_at":None,"iopv_status":"no_verified_public_feed_configured",
                 "valuation_reference":references.get(s),"calendar_source":CALENDAR_SOURCE}
            if len(q)>31:
                try:
                    at=datetime.fromisoformat(q[30]+"T"+q[31]).replace(tzinfo=CN)
                    row.update(quote_at=at.isoformat(),bid=float(q[11]),ask=float(q[21]),last=float(q[3]),
                               bid_shares=float(q[10]),ask_shares=float(q[20]),volume_shares=float(q[8]))
                except (ValueError,IndexError):row["quote_parse_error"]="invalid_fields"
            url="https://api.fund.eastmoney.com/f10/lsjz?"+urlencode({"fundCode":s,"pageIndex":1,"pageSize":5})
            text,nav_fetch=fetch(url,folder,"nav_"+s)
            row["nav_fetch"]=nav_fetch
            if text:
                try:
                    data=json.loads(text)["Data"]["LSJZList"][0]
                    row.update(nav=float(data["DWJZ"]),nav_date=data["FSRQ"])
                    key=s+"|"+row["nav_date"]+"|"+str(row["nav"])
                    state["nav"].setdefault(key,nav_fetch["first_seen_at"])
                    row["nav_first_seen_at"]=state["nav"][key]
                except (KeyError,TypeError,ValueError,IndexError):row["nav_parse_error"]="missing_valid_NAV_rows"
            decision=utc_now()
            row["observed_at"]=decision.isoformat()
            if row["nav"] and row["ask"]:
                row["ask_to_last_published_nav_minus1"]=row["ask"]/row["nav"]-1
                row["nav_valuation_age_days"]=(decision.astimezone(CN).date()-datetime.fromisoformat(row["nav_date"]).date()).days
            reference=references.get(s)
            if reference:
                reference=reference.copy()
                row["claimed_reference_first_seen_at"]=reference.get("first_seen_at")
                fingerprint=hashlib.sha256(json.dumps(reference,sort_keys=True).encode()).hexdigest()
                state.setdefault("references",{}).setdefault(fingerprint,decision.isoformat())
                reference["first_seen_at"]=state["references"][fingerprint]
                row["valuation_reference"]=reference
                row["iopv"]=reference.get("iopv")
                row["iopv_at"]=reference.get("iopv_at")
                row["iopv_method_source"]=reference.get("iopv_method_source")
                row["iopv_status"]="researcher_supplied_observation_not_automatically_verified" if row["iopv"] is not None else row["iopv_status"]
            row.update(assess_observation(row,decision,reference,args.premium_cap))
            budget=budgets.get(s)
            if budget is not None and (not isinstance(budget,(int,float)) or not math.isfinite(budget) or budget<0):
                raise ValueError("Paper budget must be a nonnegative number")
            row["paper_intended_buy_cny"]=budget
            row["paper_waiting_cash_cny"]=budget if budget is not None and row["optional_gate_eligible"] is False else None
            row["paper_waiting_status"]=("no_budget_recorded" if budget is None else "diagnostic_snapshot_only_no_execution")
            row["paper_plan_id"]=args.paper_plan_id
            if budget is not None:
                key=args.paper_plan_id+"|"+s
                wait=state.setdefault("paper_plans",{}).setdefault(key,{"first_seen_at":decision.isoformat(),"initial_budget_cny":budget})
                row["paper_plan_first_seen_at"]=wait["first_seen_at"]
                row["paper_plan_observed_age_seconds"]=(decision-datetime.fromisoformat(wait["first_seen_at"])).total_seconds()
                row["paper_budget_changed_from_initial"]=budget!=wait["initial_budget_cny"]
                row["paper_waiting_status"]="diagnostic_paused" if row["optional_gate_eligible"] is False else "diagnostic_eligible_unexecuted"
            row["counts_as_prospective_trading_day"]=row["session_status"]=="continuous_session" and row["quote_age_seconds"] is not None and 0<=row["quote_age_seconds"]<=60
            rows.append(row)
        (folder/"observations.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n")
        with (out/"observations.jsonl").open("a") as handle:
            for row in rows:handle.write(json.dumps(row,ensure_ascii=False)+"\n")
        state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n")
        all_rows=[json.loads(line) for line in (out/"observations.jsonl").read_text().splitlines()]
        flat_keys=["run_id","symbol","observed_at","quote_at","quote_first_seen_at","bid","ask","bid_shares","ask_shares",
                   "quote_age_seconds","nav","nav_date","nav_first_seen_at","nav_published_at","nav_valuation_age_days",
                   "ask_to_last_published_nav_minus1","iopv","iopv_at","iopv_method_source","iopv_status","session_status",
                   "fair_value_lower","fair_value_upper","reference_age_seconds","premium_lower","premium_upper",
                   "cap","filter_enabled","optional_gate_eligible","diagnostic_reasons","paper_intended_buy_cny",
                   "paper_waiting_cash_cny","paper_waiting_status","paper_plan_id","paper_plan_first_seen_at",
                   "paper_plan_observed_age_seconds","paper_budget_changed_from_initial","counts_as_prospective_trading_day"]
        with (out/"observations.csv").open("w") as handle:
            writer=csv.DictWriter(handle,fieldnames=flat_keys);writer.writeheader()
            for row in all_rows:
                writer.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row.get(k),list) else row.get(k) for k in flat_keys})
        trading_days=sorted({timestamp_local(r["observed_at"]) for r in all_rows if r["counts_as_prospective_trading_day"]})
        per_symbol={s:len({timestamp_local(r["observed_at"]) for r in all_rows if r["symbol"]==s and r["counts_as_prospective_trading_day"]}) for s in args.symbols}
        summary={"started_at":state["started_at"],"last_run":run_id,"samples":len(all_rows),
                 "distinct_valid_trading_days":len(trading_days),"trading_days":trading_days,
                 "required_observation_days":20,"valid_trading_days_per_symbol":per_symbol,
                 "observation_complete":all(n>=20 for n in per_symbol.values()),
                 "background_process_installed":False,"live_orders":False,
                 "automatic_current_fair_value_bounds_available":False}
        (out/"status.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    finally:lock.rmdir()


def timestamp_local(value):return datetime.fromisoformat(value).astimezone(CN).date().isoformat()


if __name__=="__main__":main()
