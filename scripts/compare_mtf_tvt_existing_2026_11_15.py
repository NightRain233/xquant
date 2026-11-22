"""Layered comparison of MTF-3/TVT-50 with the repository's frozen lines.

This is a descriptive merge of completed research outputs. It deliberately keeps
single-asset dollar/RMB results separate from the RMB multi-asset portfolio lines.
No parameters are re-selected here.
"""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "mtf-tvt-existing-comparison-2026-11-15"
HEALTH = ROOT / "outputs" / "mtf-tvt-healthcheck-2026-11-15"
OLD = ROOT / "outputs" / "strategy-comparison-2026-11-10"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    q3 = pd.read_csv(HEALTH / "summary_q3.csv")
    q5 = pd.read_csv(HEALTH / "summary_q5.csv")
    dca = pd.read_csv(HEALTH / "dca_summary.csv")
    old = pd.read_csv(OLD / "comparison.csv")
    q3 = q3[q3["cost"].eq("10bp")].copy()

    # The healthcheck is the authoritative full-history result for the new rules.
    q3["comparison_group"] = "single_asset_new_rules"
    q3["window"] = q3["asset"].map({"SPY": "2000-2026", "QQQ": "2000-2026", "513500": "2014-2026", "513100": "2014-2026"})
    q3["signal"] = q3["asset"].map({"513500": "ETF自身", "513100": "ETF自身"}).fillna("美元标的自身")
    q3.to_csv(OUT / "new_rules_q3.csv", index=False)
    q5.to_csv(OUT / "new_rules_q5.csv", index=False)
    dca.to_csv(OUT / "new_rules_dca.csv", index=False)

    keep_names = {
        "主线：三组合核心（无 BTC）",
        "主线：三组合 + 7.5% BTC 卫星",
        "冻结研究线：核心90% + Bull Flip 10%",
        "冻结研究线：核心90% + MA200过滤 Bull Flip 10%",
        "冻结研究线：风险平价核心（scan-v2）",
        "标普500 持有（SPY）",
        "标普500 半仓趋势（S2）",
        "标普500 15% 目标波动率（VT-1.0）",
        "513500 标普 持有（境内价格）",
        "513500 半仓趋势（美股信号，境内价格）",
        "513500 半仓趋势（境内信号，境内价格）",
        "513100 纳指 持有（境内价格）",
        "513100 半仓趋势（境内信号，境内价格）",
    }
    # Preserve the exact labels in the historical comparison file; the labels
    # above are matched by substring below because old notes use slight variants.
    old = old[old["strategy"].isin(keep_names) | old["strategy"].str.contains("三组合|Bull Flip|风险平价核心|标普500|513500|513100", regex=True)]
    old["comparison_group"] = old["strategy"].map(
        lambda x: "multi_asset_existing" if any(k in x for k in ("三组合", "Bull Flip", "风险平价核心")) else "single_asset_existing"
    )
    old["window"] = "2016-06-21..2026-06-23"
    old.to_csv(OUT / "existing_strategy_comparison.csv", index=False)

    # A compact table for plain-language reporting, retaining currency and source.
    report_cols = ["comparison_group", "strategy", "currency", "cagr", "vol", "sharpe", "max_dd", "calmar", "window"]
    old_report = old.rename(columns={"strategy": "strategy_name"})
    old_report = old_report.rename(columns={"strategy_name": "strategy"})
    old_report["asset"] = "仓库已有"
    new_report = q3.rename(columns={"strategy": "strategy", "asset": "asset"})
    new_report["currency"] = new_report["asset"].map({"SPY": "美元", "QQQ": "美元", "513500": "人民币", "513100": "人民币"})
    new_report["strategy"] = new_report["asset"] + " / " + new_report["strategy"]
    report = pd.concat([new_report[report_cols + ["asset"]], old_report[report_cols + ["asset"]]], ignore_index=True)
    report.to_csv(OUT / "comparison_report.csv", index=False)

    config = {
        "slug": OUT.name,
        "new_rules_source": str(HEALTH.relative_to(ROOT)),
        "existing_source": str(OLD.relative_to(ROOT)),
        "principle": "descriptive comparison; no parameter re-selection",
        "groups": {
            "single_asset_new_rules": "MTF-3/TVT-50 and buy-hold on SPY, QQQ, 513500, 513100",
            "single_asset_existing": "older S2/VT and domestic half-trend diagnostics",
            "multi_asset_existing": "repository three-asset/BTC/Bull Flip lines",
        },
        "caveat": "windows, currencies, costs and asset pools differ; do not form one overall ranking",
    }
    (OUT / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# MTF-3 / TVT-50 与仓库既有策略比较\n\n"
        "本目录只合并已完成实验，不重新挑参数。单标的美元、国内人民币 ETF、人民币多资产组合分组展示。\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
