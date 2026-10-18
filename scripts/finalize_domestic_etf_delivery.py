"""Create evidence tables, scenario figure, notebook and portable offline bundle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SLUG="domestic-etf-small-account-2026-10-04"
OUT=ROOT/"outputs"/SLUG
EVIDENCE=OUT/"evidence" if (OUT/"evidence").exists() else ROOT/"inputs/evidence"


def main():
    products=[
        ("510300","沪深300","华泰柏瑞沪深300ETF","2012-05-04","2012-05-28",.15,.05,"2024-11-20","510300_fee"),
        ("510310","沪深300","易方达沪深300ETF","2013-03-06","2013-03-25",.15,.05,"2025-11-18","510310_profile"),
        ("513100","纳斯达克100","国泰纳斯达克100ETF","2013-04-25","2013-05-15",.60,.20,"2025-03-21","513100_profile"),
        ("513300","纳斯达克100","华夏纳斯达克100ETF","2020-10-22","2020-11-05",.60,.20,"2025-05-30","513300_profile"),
        ("518880","黄金","华安黄金ETF","2013-07-18","2013-07-29",.50,.10,"2026-03-06","518880_profile"),
        ("518800","黄金","国泰黄金ETF","2013-07-18","2013-07-29",.50,.10,"2025-10-15","518800_profile"),
        ("513500","标普500","博时标普500ETF","2013-12-05","2014-01-15",.60,.20,"2026-06-26","513500_profile"),
        ("159655","标普500","华夏标普500ETF","2022-10-12","2022-10-25",.60,.15,"2025-05-30","sp500_official_audit.md"),
        ("159612","标普500","国泰标普500ETF","2022-05-09","2022-05-20",.60,.15,"2025-09-30","159612_profile"),
    ]
    metadata=pd.DataFrame(products,columns=["symbol","exposure","name","inception","listing","management_pct","custody_pct","fee_document_date","evidence_id"])
    market=pd.read_csv(OUT/"product_market_snapshot.csv",dtype={"symbol":str})
    combined=metadata.merge(market,on="symbol",validate="one_to_one")
    combined.to_csv(OUT/"product_comparison.csv",index=False)
    template=["decision_at","symbol","signal_date","signal_available_at","target_weight","held_shares",
              "bid","ask","bid_shares","ask_shares","quote_at","quote_source","nav_date","nav",
              "nav_published_at_verified","nav_first_seen_at","nav_source","iopv","iopv_at","iopv_method_source",
              "last_underlying_close_at","fx_at","fair_value_lower","fair_value_upper","reference_available_at",
              "reference_verified","reference_uncertainty_reason","pcf_date","subscription_status","issuer_warning",
              "draft_eligible","draft_reason","earmarked_cash","planned_lots","simulated_fill","actual_fill_if_future_trial",
              "actual_commission","observed_spread_bps","unfilled_amount","weight_error","minutes_spent","experience_note"]
    pd.DataFrame(columns=template).to_csv(OUT/"prospective_execution_log_template.csv",index=False)
    # A deterministic teaching scenario, not historical data or a forecast.
    days=np.arange(81)
    returns=np.column_stack([np.where(days%2==0,.012,-.012),np.where(days%2==0,.004,-.004),np.where(days%2==0,.010,-.010)])
    returns[0]=0
    nav=100*np.cumprod(1+returns,axis=0)
    premium=np.where(days<61,.20,0.)
    price=nav.copy();price[:,1]*=1+premium
    series=pd.DataFrame(price,columns=["CSI300","Nasdaq","Gold"])
    vol=series.pct_change().rolling(20).std(ddof=1)
    inverse=1/vol;weight=inverse.div(inverse.sum(axis=1),axis=0)
    no_premium_vol=pd.Series(nav[:,1]).pct_change().rolling(20).std(ddof=1)
    example=pd.DataFrame({"scenario_day":days,"nasdaq_nav":nav[:,1],"nasdaq_etf_price":price[:,1],"premium":premium,
                          "20day_daily_vol_price":vol.Nasdaq,"20day_daily_vol_nav":no_premium_vol,
                          "inverse_vol_nasdaq_target_after_close":weight.Nasdaq,
                          "prior_day_target":weight.Nasdaq.shift(),"label":"SYNTHETIC_SCENARIO_NOT_HISTORY"})
    example.to_csv(OUT/"premium_volatility_mechanism.csv",index=False)
    fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True)
    axes[0].plot(days,nav[:,1],label="Fund NAV (scenario)")
    axes[0].plot(days,price[:,1],label="ETF price: 20% premium then 0%")
    axes[0].legend();axes[0].set_ylabel("Price / NAV")
    axes[1].plot(days,weight.Nasdaq*100,label="Inverse-vol Nasdaq target after close")
    axes[1].plot(days,no_premium_vol*100,label="NAV daily volatility (%)")
    axes[1].legend();axes[1].set_ylabel("Percent");axes[1].set_xlabel("Synthetic scenario day")
    for ax in axes:ax.axvline(61,color="red",linestyle="--");ax.grid(alpha=.2)
    fig.suptitle("A stable premium is invisible to return volatility; the loss precedes reweighting")
    fig.tight_layout();fig.savefig(OUT/"premium_volatility_mechanism.png",dpi=170);plt.close(fig)
    cells=[]
    def markdown(text):cells.append({"cell_type":"markdown","metadata":{},"source":text.splitlines(keepends=True)})
    def code(text,tags=None):cells.append({"cell_type":"code","execution_count":None,"metadata":({"tags":tags} if tags else {}),"outputs":[],"source":text.splitlines(keepends=True)})
    markdown("# 境内场内ETF：5万元实施研究\n\n原始结果保留。产品快照、会计诊断、整手摩擦、溢价情景为不同证据层，不能合并为一个通过实盘验证的收益预测。详见匹配 review note。")
    code("from pathlib import Path\nimport sys\nROOT = Path.cwd().resolve()\nwhile not (ROOT / 'src' / 'xquant').exists():\n    if ROOT == ROOT.parent:\n        raise RuntimeError('Run inside the repository or portable bundle')\n    ROOT = ROOT.parent\nsys.path.insert(0, str(ROOT / 'src'))\nimport pandas as pd\nOUT = ROOT / 'outputs' / 'domestic-etf-small-account-2026-10-04'\n",["repository-root-bootstrap"])
    for title,files in [
        ("基线及会计口径诊断",["accounting_diagnostics.csv","adjustment_audit.csv"]),
        ("实际产品与可比日期",["product_comparison.csv"]),
        ("Q3/Q5诊断：不是可得投资收益",["diagnostic_q3_q5.csv","diagnostic_month_statistics.csv","diagnostic_annual.csv","diagnostic_monthly.csv","diagnostic_drawdown_events.csv"]),
        ("整手、佣金、价差与调仓频率",["pilot_execution_sensitivity.csv","50000_reference_lot_plan.csv","50000_reference_lot_plan_gated.csv"]),
        ("溢价不利情景和等待代价",["premium_shock_scenarios.csv","cash_wait_opportunity_scenarios.csv","premium_volatility_mechanism.csv"]),
        ("前瞻记录：空模板不是历史回测",["prospective_execution_log_template.csv"]),
    ]:
        markdown("## "+title)
        code("\n".join("display(pd.read_csv(OUT / "+repr(f)+"))" for f in files)+"\n")
    markdown("## 通俗结论\n\n费用条件适合小额试行，溢价与数据口径尚有门槛。三组合提供额外A股分散；两组合更集中于纳指和黄金。境内标普产品存在，不能拿SPY的成本和溢价条件代替。原10交易日规则成本可承受；月度调仓产生额外偏差，不自动替代。先模拟记录、按可得信息控制新增买入，合计试行不超过5万元；不按短期盈利追加。BTC/multi两项旧交付问题仍在范围外。")
    for index,cell in enumerate(cells):cell["id"]=f"cell-{index:02}"
    notebook={"cells":cells,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"}},"nbformat":4,"nbformat_minor":5}
    (ROOT/"research/notebooks"/(SLUG+"-practice.ipynb")).write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+"\n")
    # All computational inputs are included; reproduction needs no old output
    # directory, live endpoint, API key, SPY or external broker software.
    members={}
    for p in EVIDENCE.iterdir():
        if p.is_file():members["inputs/evidence/"+p.name]=p
    for c in ["510300","513100","518880"]:
        original=ROOT/"outputs/strategy-healthcheck-2026-10-02/market_data"/(c+".SS.parquet")
        members["inputs/frozen/"+c+".SS.parquet"]=original if original.exists() else ROOT/"inputs/frozen"/(c+".SS.parquet")
    original_ref=ROOT/"outputs/three-asset-core-2026-10-03/targets_IV20.csv"
    members["inputs/reference/targets_IV20.csv"]=original_ref if original_ref.exists() else ROOT/"inputs/reference/targets_IV20.csv"
    source_paths=["scripts/review_domestic_etf_execution.py","scripts/finalize_domestic_etf_delivery.py",
                  "src/xquant/etf_execution_research.py","src/xquant/cashflow_research.py","src/xquant/three_asset_research.py",
                  "tests/test_etf_execution_research.py","docs/notes/"+SLUG+"-review.md",
                  "research/notebooks/"+SLUG+"-practice.ipynb"]
    for name in source_paths:members[name]=ROOT/name
    members["README.md"]=OUT/"README.md" if (OUT/"README.md").exists() else ROOT/"README.md"
    for name in ["independent_audit.json","reproduction_verification.json","test_results.json","manifest.json"]:
        p=OUT/name
        if p.exists():members["outputs/"+SLUG+"/"+name]=p
    for p in OUT.glob("*.csv"):members["outputs/"+SLUG+"/"+p.name]=p
    for p in OUT.glob("*.png"):members["outputs/"+SLUG+"/"+p.name]=p
    delivery={"members":{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in members.items()},
              "description":"Offline computation inputs and evidence; no claim that historical premium availability is complete"}
    (OUT/"delivery_manifest.json").write_text(json.dumps(delivery,ensure_ascii=False,indent=2)+"\n")
    with zipfile.ZipFile(OUT/"reproduction_bundle.zip","w",zipfile.ZIP_DEFLATED) as z:
        for name,path in members.items():z.write(path,name)
        z.write(OUT/"delivery_manifest.json","delivery_manifest.json")
    print("Packaged",len(members),"files",flush=True)


if __name__=="__main__":main()
