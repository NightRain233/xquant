"""Render reader documents from delivered CSVs; no simulations or data downloads."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/etf-dividend-valuation-2026-10-04"
DEST = ROOT / "docs/strategies"
LABELS = {"Three": "三组合", "Two": "两组合", "513500": "境内标普513500"}
MODES = {"lump": "一次性投入", "dca": "定投"}


def read(name: str) -> list[dict[str, str]]:
    with (SOURCE / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def table(headers: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
                     + ["| " + " | ".join(row) + " |" for row in rows])


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def wan(value: float) -> str:
    return f"{value / 10000:.2f}"


def write_csv(name: str, rows: list[dict]) -> None:
    with (DEST / "data" / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "data").mkdir(exist_ok=True)
    audit = json.loads((SOURCE / "independent_audit.json").read_text())
    if audit.get("all_passed") is not True:
        raise ValueError("Delivered independent audit has not passed")
    summaries = {(r["strategy"], r["funding"]): r for r in read("account_summary.csv")
                 if r["variant"] == "corrected"}
    events = [r for r in read("drawdown_events.csv") if r["variant"] == "corrected"]
    if len(summaries) != 6:
        raise ValueError("Expected six corrected strategy/funding summaries")
    write_csv("holding-events.csv", events)
    frequency, months_export, source_files = [], [], ["account_summary.csv", "drawdown_events.csv", "independent_audit.json"]
    for funding, title in MODES.items():
        parts = [f"# {title}：完整持有体验", "",
                 "数据截止2026-09-30，来自完成交接的分红修订账本。下列都是历史研究结果，不是实盘成交或未来概率。读定义见[持有体验指南](holding-experience.md)。", "",
                 "## 资金与费用", "",
                 ("2015-01-05一次投入5万元，三／两组合首次正式执行为1月6日，之前持现金。" if funding == "lump" else
                  "2015年1月至2026年9月，每月第一个共同交易日开盘投入1万元，共141笔、本金141万元。"),
                 "买卖名义金额每边万分之一、无最低费用、分数份额、价差0。期末预扣一次退出佣金；分红应收计入权益但到账前不能买入。513500的全期事件完整性边界见原报告。", "", "## 最终结果与受挫频率", ""]
        headline, freq_rows, risk_rows, major_rows = [], [], [], []
        account_months = {}
        for strategy, label in LABELS.items():
            s = summaries[strategy, funding]
            ev = [r for r in events if r["strategy"] == strategy and r["funding"] == funding]
            filename = f"account_corrected_{strategy}_{funding}.csv"
            source_files.append(filename)
            account = read(filename)
            values = {r["date"]: r for r in account}
            if abs(float(account[-1]["liquidation_wealth"]) - float(s["terminal_liquidation"])) > 1e-6:
                raise ValueError("Terminal account does not match summary")
            observed_dd = min(float(r["unit_drawdown"]) for r in account)
            if abs(observed_dd - float(s["unit_max_drawdown"])) > 1e-10:
                raise ValueError("Drawdown does not match summary")
            headline.append([label, wan(float(s["terminal_liquidation"])), wan(float(s["profit"])),
                             pct(float(s["xirr"])), pct(observed_dd)])
            counts = [sum(float(r["depth"]) <= -threshold for r in ev) for threshold in (.05, .10, .15, .20)]
            major = [r for r in ev if float(r["depth"]) <= -.05]
            completed = [int(r["underwater_calendar_days"]) for r in major if r["censored"] == "False"]
            freq_rows.append([label, *map(str, counts), str(max(int(r["underwater_calendar_days"]) for r in ev)),
                              str(statistics.median(completed)) if completed else "无", str(sum(r["censored"] == "True" for r in major))])
            frequency.append({"strategy": strategy, "funding": funding,
                              **{f"events_ge_{threshold}pct": count for threshold, count in zip((5, 10, 15, 20), counts)},
                              "all_events": len(ev), "completed_major_recovery_median_days": statistics.median(completed) if completed else "",
                              "longest_observed_underwater_days": max(int(r["underwater_calendar_days"]) for r in ev)})
            profit_peak = float(account[0]["profit"])
            giveback = 0.0
            negative_events, was_negative = 0, False
            monthly = {}
            previous = float(account[0]["pre_flow_unit_price"])
            for r in account:
                profit = float(r["profit"])
                profit_peak = max(profit_peak, profit)
                giveback = max(giveback, profit_peak - profit)
                neg = profit < -1e-8
                negative_events += int(neg and not was_negative)
                was_negative = neg
                key = r["date"][:7]
                if key not in monthly:
                    monthly[key] = {"month": key, "previous_unit": previous, "contribution": 0.0, "cost": 0.0, "market_pnl": 0.0,
                                    "month_open_wealth": float(r["wealth"]) - float(r["contribution"]) - float(r["market_pnl"]) + float(r["cost"]),
                                    "minimum_unit_drawdown": 0.0}
                m = monthly[key]
                for k in ("contribution", "cost", "market_pnl"):
                    m[k] += float(r[k])
                m["minimum_unit_drawdown"] = min(m["minimum_unit_drawdown"], float(r["unit_drawdown"]))
                m.update(month_end_wealth=float(r["wealth"]), month_end_principal=float(r["principal"]),
                         month_end_liquidation=float(r["liquidation_wealth"]), month_end_profit=profit,
                         month_end_unit=float(r["unit_nav"]))
                previous = float(r["unit_nav"])
            for m in monthly.values():
                m["return"] = m["month_end_unit"] / m["previous_unit"] - 1
                residual = m["month_end_wealth"] - (m["month_open_wealth"] + m["contribution"] + m["market_pnl"] - m["cost"])
                if abs(residual) > 1e-6:
                    raise ValueError(f"Monthly account conservation failed: {strategy} {funding} {m['month']}")
                months_export.append({"strategy": strategy, "funding": funding, **m})
            account_months[strategy] = monthly
            losing = [m for m in monthly.values() if m["return"] < 0]
            risk_rows.append([label, str(negative_events), f"{float(s['worst_loss_amount']):,.0f}", pct(float(s["worst_loss_ratio"])),
                              str(s["longest_completed_principal_loss_days"]), wan(giveback), f"{len(losing)}/{len(monthly)}"])
            for r in major:
                peak_account = float(values[r["peak"]]["wealth"])
                trough_account = float(values[r["trough"]]["wealth"])
                major_rows.append([label, r["peak"], r["trough"], r["recovery"] or "未恢复", pct(float(r["depth"])),
                                   r["underwater_calendar_days"], f"{wan(peak_account)}→{wan(trough_account)}"])
        parts += [table(["方案", "期末净权益（万元）", "净盈利（万元）", "历史XIRR", "单位最大回撤"], headline), "",
                  "XIRR包含入金日期和末期退出估值，不是未来预测。一次投入与定投本金不同，不能直接比较两页终值决定哪种入金更优。", "",
                  table(["方案", "≥5%事件", "≥10%", "≥15%", "≥20%", "最长观测水下天数", "≥5%已恢复中位天数", "≥5%未恢复事件"], freq_rows), "",
                  "门槛统计有包含关系，不能相加。同一高点直到恢复的反复下跌只算一个事件。中位数只涵盖已恢复的≥5%事件，未恢复单列；最长观测时间可能包含未结束事件。次数是本样本记录，不代表未来频率。", "",
                  "## 本金与利润的真实压力", "",
                  table(["方案", "低于本金事件数", "最大本金亏损（元）", "最大本金亏损比例", "最长已恢复本金亏损天数", "最大盈利回吐（万元）", "亏损月／全部月"], risk_rows), "",
                  "极小的买入／退出费用也可能产生短暂本金亏损，因此事件次数不能单独表示严重程度。金额与比例的最差日可能不同。盈利回吐从每日净权益减累计本金计算，新增本金已剔除，但新增资金的后续损益仍包括在内。", "",
                  "这是2015年起投主账户，早期利润缓冲不能代表其他起点。定投滚动账户的370／160／177天等待与这里主账户最长等待是不同口径，不能混用。", "",
                  "## 每一次至少5%的回撤", "",
                  table(["方案", "高点", "低点", "恢复或未恢复", "深度", "峰到恢复／截止天数", "账户权益高→低（万元）"], major_rows), "",
                  "定投权益金额含期间入金，高点金额到低点金额不等于剔除入金的损失；深度来自单位净值。各方案分别恢复自己的前高。更浅事件也完整保存在[全部事件CSV](data/holding-events.csv)。", "",
                  "## 最近36个月，按月打开账户", "",
                  "下表不是2023年重新投入的新账户，而是上述2015年起投账户在2023-10至2026-09的月末快照。收益列剔除入金，权益列含累计现金流；月中回撤和每月入金、损益、费用详见[完整月度账户CSV](data/holding-months.csv)。", ""]
        month_rows = []
        for key in sorted(account_months["Three"]):
            if "2023-10" <= key <= "2026-09":
                row = [key]
                for strategy in LABELS:
                    m = account_months[strategy][key]
                    row.extend([pct(m["return"]), wan(m["month_end_wealth"])])
                month_rows.append(row)
        parts += [table(["月份", "三组合收益", "权益万元", "两组合收益", "权益万元", "513500收益", "权益万元"], month_rows), "",
                  "月底赚钱不能说明月中平静；国内休市日沿用已有收盘也不说明海外资产没有风险或可以立即退出。", "",
                  "## 证据与再生成", "",
                  "[完整研究报告](../notes/etf-dividend-valuation-2026-10-04-review.md) · [复现说明](../../outputs/etf-dividend-valuation-2026-10-04/README.md) · [文档来源SHA](data/holding-provenance.json)", "",
                  "本页由 `scripts/render_core_holding_docs.py` 读取交付CSV生成，没有下载行情、运行新回测或改写研究产物。公司行动资料、价差与券商执行边界仍继承源报告。", ""]
        (DEST / f"holding-{funding}.md").write_text("\n".join(parts))
    write_csv("holding-frequency.csv", frequency)
    write_csv("holding-months.csv", months_export)
    provenance = {"source_slug": SOURCE.name, "source_cutoff": "2026-09-30", "generated_from_delivered_csv_only": True,
                  "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "sources": {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in source_files}}
    (DEST / "data/holding-provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    print(f"Generated two holding documents, {len(events)} events, {len(months_export)} monthly account rows; summary/DD/monthly conservation checks passed.")


if __name__ == "__main__":
    main()
