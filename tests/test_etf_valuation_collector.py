"""Offline synthetic collector fixtures; never saved as real research samples."""
import importlib.util
import json
from pathlib import Path
import sys

from xquant.etf_valuation_monitor import timestamp


def collector():
    path=Path(__file__).resolve().parents[1]/"scripts/collect_etf_valuation.py"
    spec=importlib.util.spec_from_file_location("collector_under_test",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_sources(clock):
    fields=["0"]*33
    fields[3]="2.005";fields[11]="2.0";fields[21]="2.01"
    fields[30]="2026-10-08";fields[31]="10:00:00"
    def fetch(url,folder,name,encoding="utf-8"):
        text='var hq_str_sh513100="'+','.join(fields)+'";' if name=="quotes" else json.dumps({"Data":{"LSJZList":[{"DWJZ":"1.9","FSRQ":"2026-09-29"}]}})
        return text,{"status":"ok","first_seen_at":clock[0].isoformat(),"url":url}
    return fetch


def test_real_first_seen_clock_is_preserved_and_repeated_day_counts_once(tmp_path,monkeypatch):
    module=collector();clock=[timestamp("2026-10-08T10:00:05+08:00")]
    monkeypatch.setattr(module,"utc_now",lambda:clock[0])
    monkeypatch.setattr(module,"fetch",fake_sources(clock))
    monkeypatch.setattr(sys,"argv",["collect","--output",str(tmp_path),"--symbols","513100"])
    module.main()
    clock[0]=timestamp("2026-10-08T10:00:10+08:00");module.main()
    rows=[json.loads(line) for line in (tmp_path/"observations.jsonl").read_text().splitlines()]
    assert len(rows)==2
    assert rows[0]["nav_first_seen_at"]==rows[1]["nav_first_seen_at"]==timestamp("2026-10-08T10:00:05+08:00").isoformat()
    assert rows[1]["nav_date"]=="2026-09-29"
    assert rows[1]["nav_published_at"] is None
    status=json.loads((tmp_path/"status.json").read_text())
    assert status["valid_trading_days_per_symbol"]["513100"]==1
    assert status["observation_complete"] is False
    assert not (tmp_path/".collection.lock").exists()


def test_imported_reference_clock_cannot_backfill_its_real_first_seen(tmp_path,monkeypatch):
    module=collector();clock=[timestamp("2026-10-08T10:00:05+08:00")]
    monkeypatch.setattr(module,"utc_now",lambda:clock[0]);monkeypatch.setattr(module,"fetch",fake_sources(clock))
    ref=tmp_path/"reference.json"
    ref.write_text(json.dumps({"513100":{"first_seen_at":"2026-09-29T10:00:00+08:00","researcher_verified":False}}))
    monkeypatch.setattr(sys,"argv",["collect","--output",str(tmp_path/"observations"),"--symbols","513100","--references",str(ref),"--premium-cap","0.01"])
    module.main()
    row=json.loads((tmp_path/"observations/observations.jsonl").read_text().splitlines()[0])
    assert row["claimed_reference_first_seen_at"]=="2026-09-29T10:00:00+08:00"
    assert row["valuation_reference"]["first_seen_at"]==clock[0].isoformat()
    assert row["optional_gate_eligible"] is False
