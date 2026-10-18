"""Render dated accounting/monitor review and a portable frozen-input bundle."""
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
SLUG="etf-dividend-valuation-2026-10-04"
OUT=ROOT/"outputs"/SLUG


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def annotation():
    updates=[]
    for name in ["three-asset-core-2026-10-03-review.md","dca-comparison-2026-10-04-review.md","domestic-etf-small-account-2026-10-04-review.md"]:
        path=ROOT/"docs/notes"/name
        if not path.exists():continue
        original=OUT/"legacy_notes"/name
        original.parent.mkdir(exist_ok=True)
        if not original.exists():original.write_bytes(path.read_bytes())
        marker="> **分红会计口径更新（2026-10-04）**"
        if marker not in path.read_text():
            note=marker+"：本文及原CSV保留为旧研究口径。510300加法前复权不能代替原始份额、除息应收和现金到账账本，也可能改变20日逆波动权重。优先采用[分红修正报告](etf-dividend-valuation-2026-10-04-review.md)的相同费用比较；本文原文已逐字节保存在新输出的legacy_notes目录。两组合在已核查事件下不受510300修正影响；境内标普500仍有事件完整性边界。此更新不关闭BTC/多资产此前两项交付问题。\n\n"
            path.write_text(note+path.read_text())
        updates.append({"note":name,"archived_original_sha256":sha(original),"annotated_live_sha256":sha(path)})
    if updates:(OUT/"legacy_note_annotations.json").write_text(json.dumps(updates,ensure_ascii=False,indent=2)+"\n")


def figures():
    colors={"Three":"#2166ac","Two":"#d6604d","513500":"#444444"}
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,layout="constrained")
    for strategy in colors:
        d=pd.read_csv(OUT/f"account_corrected_{strategy}_lump.csv",index_col=0,parse_dates=True)
        axes[0].plot(d.index,d.unit_nav,label=strategy,color=colors[strategy])
        axes[1].plot(d.index,d.unit_drawdown*100,label=strategy,color=colors[strategy])
    old=pd.read_csv(OUT/"account_legacy_additive_Three_lump.csv",index_col=0,parse_dates=True)
    axes[0].plot(old.index,old.unit_nav,linestyle="--",color="#92c5de",label="Three legacy additive")
    axes[0].set_ylabel("Unit NAV (initial 1)");axes[1].set_ylabel("Drawdown (%)")
    axes[0].set_title("Frozen ETF prices, official distributions, IV20 / fixed calendar")
    for ax in axes:ax.grid(alpha=.2);ax.legend(loc="upper left",fontsize=8)
    fig.savefig(OUT/"corrected_nav_drawdown.png",dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4),layout="constrained")
    for strategy in colors:
        d=pd.read_csv(OUT/f"account_corrected_{strategy}_dca.csv",index_col=0,parse_dates=True)
        ax.plot(d.index,d.profit/10000,label=strategy,color=colors[strategy])
    ax.set_title("CNY 10,000 per month: net equity less contributed principal")
    ax.set_ylabel("Profit (CNY 10,000)");ax.grid(alpha=.2);ax.legend()
    fig.savefig(OUT/"corrected_dca_profit.png",dpi=160);plt.close(fig)


def attribution():
    rows=[]
    for strategy in ["Three","Two","513500"]:
        for mode in ["lump","dca"]:
            daily=pd.read_csv(OUT/f"account_corrected_{strategy}_{mode}.csv")
            components={c.removeprefix("price_pnl_"):daily[c].sum() for c in daily if c.startswith("price_pnl_")}
            components["510300_cash_dividend_income"]=daily.dividend_income.sum()
            components["commission"]=-daily.cost.sum()
            residual=daily.wealth.iloc[-1]-daily.principal.iloc[-1]-sum(components.values())
            assert abs(residual)<1e-6
            for component,value in components.items():
                rows.append({"strategy":strategy,"funding":mode,"component":component,"pnl_cny":value,
                             "portfolio_terminal_wealth_less_principal":daily.wealth.iloc[-1]-daily.principal.iloc[-1],
                             "reconciliation_residual":residual})
    pd.DataFrame(rows).to_csv(OUT/"pnl_attribution.csv",index=False)


def table_summary(summary,mode):
    rows=["|组合|投入本金|期末扣退出佣金权益|净赚|单位净值最大回撤|最长未创新高|",
          "|---|---:|---:|---:|---:|---:|"]
    q=pd.read_csv(OUT/"q3_q5.csv")
    for strategy,name in [("Three","三组合"),("Two","纳指＋黄金"),("513500","境内标普513500")]:
        s=summary[(summary.variant=="corrected")&(summary.strategy==strategy)&(summary.funding==mode)].iloc[0]
        m=q[(q.variant=="corrected")&(q.strategy==strategy)&(q.funding==mode)].iloc[0]
        rows.append(f"|{name}|{s.principal/10000:.2f}万元|{s.terminal_liquidation/10000:.2f}万元|{s.profit/10000:.2f}万元|{s.unit_max_drawdown:.2%}|{m.longest_underwater_days:.0f}天|")
    return "\n".join(rows)


def render():
    summary=pd.read_csv(OUT/"account_summary.csv")
    worst=pd.read_csv(OUT/"rolling_dca_worst.csv")
    risk=pd.read_csv(OUT/"rolling_dca_risk_summary.csv")
    latest=pd.read_csv(OUT/"targets_IV20_corrected.csv",index_col=0).iloc[-1]
    sources=pd.read_csv(OUT/"dividend_events.csv",dtype={"fund_code":str})
    old=summary[(summary.variant=="legacy_additive")&(summary.strategy=="Three")].set_index("funding")
    new=summary[(summary.variant=="corrected")&(summary.strategy=="Three")].set_index("funding")
    rows=["|组合|最差36个月定投期末收益/本金|最差60个月定投期末收益/本金|滚动账户中最大本金亏损|最长一次回本等待|",
          "|---|---:|---:|---:|---:|"]
    for strategy,name in [("Three","三组合"),("Two","纳指＋黄金"),("513500","境内标普513500")]:
        a=worst[(worst.strategy==strategy)&(worst.months==36)].iloc[0]
        b=worst[(worst.strategy==strategy)&(worst.months==60)].iloc[0]
        r=risk[(risk.strategy==strategy)&(risk.months==36)].iloc[0]
        rows.append(f"|{name}|{a.profit_on_principal:.2%}|{b.profit_on_principal:.2%}|{r.worst_intra_account_loss_cny:,.0f}元（当时本金{r.principal_at_worst_loss:,.0f}元）|{r.longest_completed_principal_loss_days:.0f}天|")
    coverage=json.loads((OUT/"monitor/coverage_summary.json").read_text())
    samples=sum(r["all_real_collection_samples"] for r in coverage)
    status=json.loads((OUT/"monitor/status.json").read_text())
    report=f"""# 三组合分红会计修正与海外ETF估值监测：2026-10-04

## 结论先看

**历史事实：分红修正改变了三组合的收益数字，没有反转本样本的组合排序。** 相同万分之一佣金下，5万元一次投入的三组合期末权益由{old.loc['lump','terminal_liquidation']/10000:.2f}万元降为{new.loc['lump','terminal_liquidation']/10000:.2f}万元；每月1万元定投由{old.loc['dca','terminal_liquidation']/10000:.2f}万元降为{new.loc['dca','terminal_liquidation']/10000:.2f}万元。两组合历史赚得更多，三组合回撤较浅，境内513500的跌幅与回撤等待更大。不能把这个排序外推成未来优劣。

**实测事实：自动保存报价和最新已公布净值可运行，但尚未建立可靠、容易执行的盘中公允价值区间。** 有报价时间，NAV只有所属日期，没有可核验的精确发布时刻；工具记录实际第一次看到的时刻。现有免费日线、Sina盘口、Eastmoney净值和TickFlow已核查的Quote schema，不能直接提供覆盖股票时差、汇率、持仓跟踪误差的当前估值区间。普通小账户不宜把这一缺口包装成精确的溢价判断。

**观察未完成：无法判断过滤是否经常使人买不了。** 目前{samples}条真实采集样本（含失败净值响应）都来自10月4日休市期间，各产品有效交易日记录为0/20。休市/旧报价/区间未核实导致的暂停，不能算作交易日的高溢价暂停率。原国内ETF成交价IV20无过滤方案继续为基线，任何溢价门槛都只作可选执行变体；1%不默认启用，也未证明收益更好。

## 一、事件证据与会计约定

**官方事实。** 510300自成立至2026-09-30共核查14次现金分红，合计0.88元/份，14条均有原公告原件；2015年以来账本涉及12次。登记日、除息日和发放日分别保存于[事件表](../../outputs/{SLUG}/dividend_events.csv)。2015公告原件路径的发布日期目录和文件名不同：[官方原件](https://www.sse.com.cn/disclosure/fund/announcement/c/2015-01-13/510300_20150114_1.pdf)确认登记1/19、除息1/20、投资者发放1/23；管理人1/21划中登、中登1/22划券商，不能将前两个日期当作个人可用现金。

513100按官方1:5比例，2022-01-12登记、1/13停牌折算、1/14恢复交易；513500按官方1:2比例，2022-03-28登记、3/29停牌折算、3/30复牌。账本在官方折算日收盘变更份额，暂停日沿用的旧价格同步除以比例，权益不凭空增减；信号在首个复牌价格上消除机械拆分跌幅。518880的2013年上市前折算已在2015年之前，不再次对交易所原始行情折算。

**完整性边界。** 513100和518880管理人现有事件表未列现金分红；513500的[2025年度报告](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-03-31/513500_20260331_LQSH.pdf)确认过去三年无利润分配。另见 other_funds_evidence.md 中补充核查。这些证据不能扩大成全生命周期没有遗漏事件的审计保证，尤其513500的2015—2022及2026全年完整事件册仍需补强；对照采用“已取得记录未发现其他现金分红”的条件。510300的14条现金事件已补齐原件。

**研究约定。** 收盘登记的实际持有份额决定权益；除息日开盘前生成应收。除息当天卖出不丢掉应收，当天新买入不取得此前登记的权益。应收进入总权益和外部入金的单位净值，但绝不能用于买入。官方发放日没有券商精确入账时刻，因此主模型保守在当天收盘后转为现金；分红现金等到下一次原日历调仓才参与再投资。非调仓日的月度入金只花新入金，不顺便预支应收或改变调仓频率。真实试行以券商已显示可用资金为准；若券商更晚入账，应继续等待。现金0收益；不重复扣基金内部已包含的费用/税负。

## 二、信号与成交分开

**固定基线。** 510300、513100、518880，20个原共同交易日收益的样本标准差（ddof=1）取倒数；原 targets_IV20.csv 的signal_date与下一开盘执行日逐项保留。无杠杆、无趋势退出、无溢价过滤，没有窗口/权重/日历调参。最新冻结目标权重约为沪深300 {latest['510300']:.2%}、纳指 {latest['513100']:.2%}、黄金 {latest['518880']:.2%}，仅供口径核对，不是当前订单。

普通日信号收益为 `收盘价/前收盘价−1`；现金除息日为 `(收盘价＋每份现金分红)/前收盘价−1`；拆分后首报价日为 `收盘价×官方拆分比例/拆分前收盘价−1`。先在标的原生行情日上计算、向前连乘为因果收益指数，再按原共同日历取收益，以覆盖共同日历中跳过的单基金停牌日。分红只影响除息日及以后的信号，不倒扣过去价格；未来新增分红不能改写过去20日收益或权重。事件公告日期早于相关除息/拆分，日期不足以声明精确发布时间，未伪造历史时刻；拆分事前计划与事后精确比例确认分别列明。

信号指数只是消除机械除息/拆分的收益序列，**不代表账户提前拿到现金、更不代表自动除息再投资**。实际成交用未复权开盘价，持仓用未复权收盘价及暂停日一致估值，分红现金和应收独立记账。三个层次分别导出 signal_native_returns、targets_IV20_corrected、逐日account/fills/events和signal_clock_audit。510300目标权重与旧加法口径最大差约6.05个百分点。

## 三、同口径比较

**历史模型结果，窗口2015-01-05至2026-09-30。** 一次投入5万元，沿用原信号/首个执行日2015-01-06（之前持现金）；定投每个共同交易月首开盘投入1万元，共141次，本金141万元，首次2015-01-05按上一已知信号投入。三组合、两组合原10共同交易日调仓；513500为单标的买入持有及月度新增，不制造无意义卖买。所有方案按每笔实际买/卖名义金额收万分之一，期末净权益扣相同退出佣金。分数份额、无最低收费、价差为0的研究主口径，不是5万元整手实盘复制；此前小账户整手/5及20bps价差诊断仍保留，不能直接沿用旧三组合权重作为修正策略的真实收益。

一次投入：

{table_summary(summary,'lump')}

每月定投：

{table_summary(summary,'dca')}

最大回撤是从账户单位净值高点跌下来多少，不是投入本金亏多少；持续入金会掩盖简单账户余额的下跌。“最长未创新高”不等于本金回本等待。固定2015年起投的本金亏损很小，不能据此认定其他时间开始也很安全。

每个月重新开一个定投账户，完整36/60个月各106/82个窗口，各组合共188个，三方案共564个独立账户：

{chr(10).join(rows)}

表中最差期末、途中最亏和最长回本来自各自不同账户，不应拼成一条不存在的路径。三组合最差36个月是2019-11至2022-10，期末只比本金多约0.46%；最差60个月为2017-11至2022-10，约22.13%。两组合对应最差期末仍较好，但不能证明未来更好。回本等待从低于累计本金开始，到首次回到本金（已扣假想退出佣金），按日历天计；末期仍未回本会另标删失，不能用窗口终止冒充回本。CSV另有单位净值滚动3/5年、年度/月度、Sharpe/Sortino/Calmar及回撤事件。

**哪些旧结论保留。** 本样本两组合最终收益较高、三组合峰值回撤较浅、标普513500回撤更大；分散资产池和逆波动只是配置方法，不保证未来赚钱；低波动识别不了稳定高溢价。两组合相同费用曲线与旧口径一致（官方5倍拆分确认后，持仓单位转换不改变权益）。

**哪些改变。** 三组合的绝对收益、权重、具体回撤/回本数字应以新账本为准。旧加法复权的三组合定投终值416.41万元，下修至404.44万元，约少11.96万元；一次投入终值少约1.51万元（约5.32%）。这不是“额外扣了一次分红”，而是修正价格口径、信号及现金再投资时点。raw_cash_old_weights 控制组将会计修正与权重修正分开，不能把全部差异归因于现金晚到。此前不同10bps费用结果仍是旧成本历史资料，不与本轮1bp混比。

## 四、海外估值流程：已证实什么

本轮从 **{status['started_at']}（UTC）** 开始追加真实记录，绝不把9月29日NAV倒填成当时已知。Sina提供盘口和报价标签；Eastmoney提供最新公布NAV及所属日期，本轮只能核实收到响应的时刻。首轮因Referer返回业务空响应，已保存并修复；后续成功取得五产品NAV。价格标签仍停在9月30日，净值所属日期9月29日；10月4日看到这些值，不表示它们9月30日某时刻已经公开。

**实测限制。** 没有接通经核实的实时IOPV数据；没有持仓/PCF资产明细、相应海外股票/期货和汇率的统一可靠时钟及有依据误差上界。已冻结TickFlow官方OpenAPI，Quote字段包含成交行情，没有IOPV/基金公允价值区间；不能从免费历史日线推断盘中净值。Sina/净值接口是否能在20个真实交易日稳定满足60秒报价新鲜度，仍未实测。IOPV即使显示刷新，也可能使用已完成海外收盘与人民币中间价，不能视作全天实时可兑现净值。

参考区间若未来采用 `最新已公开NAV×已完成指数变动×汇率变动`，只能作为研究估算；必须说明NAV估值汇率、指数总/价格收益口径、基金持仓/现金/期货/税费跟踪误差以及时间一致性。今天没有这些误差边界，不能凭空加±1%就称可靠区间，更不能假装1%门槛能被精确执行。已有公开价/NAV比值只能作为陈旧参考粗筛，不当作真实溢价。

## 五、工具与长期记录

[采集工具](../../scripts/collect_etf_valuation.py)一次运行完成：五产品实际买卖盘、NAV、请求起止/收到时间、原始响应SHA、报价陈旧秒数、净值所属日期、真实首次见到时间、估值依据（缺失就留空）、暂停诊断和可选纸面预算等待。JSONL与原始响应追加保留，CSV是其派生视图；同NAV修订值使用新指纹，重复采集不会把首次见到时刻提前。研究者输入的参考区间也按本工具真实首次接收计时，不信任手填的历史可得时刻。锁避免两个采集进程交叉写；崩溃残留锁须确认无运行进程后手工清理，正常失败会记错误并继续。

默认只观察，**不设任何溢价门槛**。`--premium-cap`明确指定才产生纸面过滤结果。报价旧/不在连续竞价/缺少可核实当前区间/公告状态未核查，各自保留原因；不能把它们归入高溢价。区间的保守下界用于判断最坏购买溢价，上界给出区间另一端。手工参考模板是未核实空模板，填数并勾选也不构成估值方法已经独立通过。已有持仓没有自动清仓指令，基线调仓保持独立；过滤不是卖出保护。

`--paper-budgets`和`--paper-plan-id`仅记录假想购买预算、计划真实首次记录时刻、观察年龄和暂停快照，不扣款、不成交、不算实际账户现金。随包1000元示例是五个独立纸面意向，不是已经等待的真实资金，观察年龄也不是持续暂停时长；真实纸面计划需自行录入预算与完成/取消记录。等待造成的错过上涨属于代价，不能预设过滤提高收益。

**长期运行建议，尚未安装。** 在实际连续交易时段09:40、10:40、14:00各手动运行一次；需要自动化可由你以后主动配置cron/launchd，保持机器联网开机，记录失败并备份目录。本轮没有安装定时任务、启动后台服务或默认未来继续运行。2026日历按上交所官方节假日核实，10月8日恢复交易；2027年必须更新官方日历，工具届时标未核实并不计有效观察。20日按每产品真实交易时段且报价≤60秒的不同日期累计，同一天跑多次仍算1天；还要单独看估值完整性，20天采到报价不等于估值可靠。

在积累到20个有效交易日之前，报告不提供“经常买不了”的精确百分比。后续先分别统计有效观察缺数据率、估值未知暂停、公告/临停暂停、真正超过指定门槛的暂停、纸面预算等待及错过上涨；多次日内快照相关，不能当独立样本扩大可信度，也不要寻找最赚钱门槛。

## 六、验证、复现和范围

主计算使用uv，复用冻结原价、旧价格和日历，一次准备后两个进程计算独立窗口；预检单账户约0.22—0.26秒，本机已测完整计算约37—46秒。新函数、离线采集集成与原共享核算测试共34项通过。独立复核核对两个4287日账本、各37个事件阶段、9794条底层收益及全部286次权重；账户差异低于1×10⁻⁸元，权重最大差约3.4×10⁻¹⁴。详见 independent_audit.json，只声明已复核的公式与账户，不能扩大成真实券商结算或所有历史停牌/盘口均可成交。

完整证据、运行环境、计算输入/代码/输出SHA和离线命令见[README](../../outputs/{SLUG}/README.md)及reproduction_bundle.zip。旧报告加了口径提示，完整原文逐字节归档，旧CSV/冻结价格未覆盖。日线开盘价不是成交保证，历史停牌导致延迟开市的首笔价可能不在09:30；无历史精确报价、分红税务与券商到账记录、撮合和结算约束。收益包含二级市场历史溢价变化，不能另重复扣一遍溢价。

**最终回答。** 分红修正改变三组合数字，不反转本样本排序；报价/NAV记录流程可运行，严格当前估值仍不可靠且不够省事；过滤是否经常无法买入目前未知。先保持无过滤基线与纸面变体并列，验证估值与执行成本后再决定是否实际采用。所有收益是历史模型结果，不是未来预测；本轮没有交易。BTC/多资产未重跑，其此前两项交付问题仍未关闭。
"""
    (ROOT/"docs/notes"/(SLUG+"-review.md")).write_text(report)


def notebook():
    cells=[]
    def add(kind,source,tags=None):
        c={"cell_type":kind,"id":f"{SLUG}-{len(cells)}","metadata":{},"source":source.splitlines(keepends=True)}
        if tags:c["metadata"]["tags"]=tags
        if kind=="code":c.update(execution_count=None,outputs=[])
        cells.append(c)
    add("markdown","# 三组合分红修正与海外估值记录\n\n固定IV20和原日历。数据层、会计层、信号层和可选过滤分别研究。详见匹配review。")
    add("code","from pathlib import Path\nimport sys\nROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src/xquant').exists())\nsys.path.insert(0, str(ROOT / 'src'))\nimport pandas as pd\nOUT = ROOT / 'outputs' / '"+SLUG+"'\n",["repository-root-bootstrap"])
    for title,file in [("事件与时钟","corporate_actions.csv"),("新旧口径同费用比较","account_summary.csv"),("Q3/Q5指标","q3_q5.csv"),("月度与年度","monthly.csv"),("年度","annual.csv"),("回撤与回本","drawdown_events.csv"),("滚动定投风险","rolling_dca_risk_summary.csv"),("成本敏感性：不改变窗口或日历","cost_sensitivity.csv")]:
        add("markdown","## "+title)
        add("code","pd.read_csv(OUT / '"+file+"')\n")
    add("markdown","## 海外监测：实际采集，不补历史\n\n0/20有效交易日。样本在休市日取得，不能判断过滤暂停频率，工具默认不启用门槛。")
    add("code","pd.read_csv(OUT / 'monitor/observations.csv')\n")
    add("markdown","![NAV and drawdown](../../outputs/"+SLUG+"/corrected_nav_drawdown.png)\n\n会计修正下修三组合收益，不反转本样本排序；当前估值区间未验证；过滤频率未知。历史年化不作预测，BTC/多资产两项交付问题尚未关闭。")
    document={"cells":cells,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python","version":"3.12"}},"nbformat":4,"nbformat_minor":5}
    (ROOT/"research/notebooks"/(SLUG+"-practice.ipynb")).write_text(json.dumps(document,ensure_ascii=False,indent=1)+"\n")


def readme():
    (OUT/"README.md").write_text("""# 三组合分红会计修正与海外估值记录

研究截止2026-09-30；前瞻采集从实际2026-10-04开始。无实际交易，无后台持续任务。原策略IV20、日历和资产池固定，溢价门槛默认不启用。

## 离线复算

将 reproduction_bundle.zip 解压到空目录，进入解包根目录。第一次安装固定Python包可能需要网络，计算不需要行情网络：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 python scripts/review_etf_dividend_valuation.py --workers 2
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with matplotlib==3.11.0 python scripts/finalize_etf_dividend_valuation.py
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pytest==9.0.2 python -m pytest tests/test_etf_dividend_accounting.py tests/test_etf_valuation_monitor.py tests/test_etf_valuation_collector.py tests/test_cashflow_research.py tests/test_three_asset_research.py tests/test_etf_execution_research.py -q
```

旧代码、原价、旧复权价格与调仓参考均随包，不需要BTC/多资产冻结数据或SPY。

## 采集真实样本

在项目或解包根目录运行；这是联网一次性研究采集，不发订单，也不安装定时器：

```sh
uv run --no-project python scripts/collect_etf_valuation.py
uv run --no-project python scripts/summarize_etf_observations.py
```

可选纸面门槛示例，1%只是此前草案，参数不设置时只观察：

```sh
uv run --no-project python scripts/collect_etf_valuation.py --premium-cap 0.01 --paper-budgets outputs/etf-dividend-valuation-2026-10-04/monitor/paper_budget_example.json --paper-plan-id illustrative-only-2026-10-04
```

示例中的五个1000元是独立假想意向，非真实入金/账户余额/交易。纸面计划年龄从首次真实记录算起，不表示一直处于暂停状态。更换预算/计划须记录，工具不会伪造历史等待。`--references`接受空模板格式的研究者参考区间，但当前没有被独立证明可靠的自动估值方法，不应随意填数字开启买入判断。

建议真实交易时段09:40/10:40/14:00采集。手动运行可以积累；长期自动运行需你另行配置cron/launchd并维护联网主机，本次没有安装。正常异常留下原始错误继续采集，硬中断残留`.collection.lock`须确认没有另一采集进程后才清理。2026日历有官方依据，2027需更新。报价≤60秒且在连续交易时段才计有效交易日，按每产品不同日期计数，不把重复采集当多天。20日还只是报价覆盖，估值可靠性单独评估。

JSONL/raw为原始追加记录，CSV与coverage_summary/status为派生视图。最新NAV日期≠披露时刻，nav_published_at未知留空，nav_first_seen_at为本工具确实首次收到时刻。最新NAV比值不等于当前真实溢价；IOPV与区间缺失明确保留。回顾快照不倒填到历史观察。门槛结果仅纸面诊断，原IV20价格基线保持无过滤。休市和估值未知不能计入“真实高溢价导致买不了”的频率。

## 会计及证据

corporate_actions/dividend_events列官方登记、除息、发放及拆分记录。原始价格与收益信号分开；应收计入权益不计可买现金，发放日收盘后转现金，下一原调仓日再投资。主比较为分数份额、每边名义成交万分之一、价差0的历史模型，非整手实盘承诺。全部新CSV与旧口径桥接、564独立滚动定投、月年/回撤/成本敏感性单独交付。独立核查见 independent_audit.json 与verify脚本；来源原件、原始失败响应、SHA及旧报告完整原文随包。

最终通俗结论见 docs/notes/etf-dividend-valuation-2026-10-04-review.md。分红修正下修三组合终值，未反转样本排序；当前估值区间未建立；20日未完成，过滤暂停频率未知。历史收益不作预测。BTC/多资产未重跑，两项旧交付问题仍未关闭。
""")


def package():
    source=["scripts/review_etf_dividend_valuation.py","scripts/finalize_etf_dividend_valuation.py",
            "scripts/review_domestic_etf_execution.py","scripts/collect_etf_valuation.py","scripts/summarize_etf_observations.py",
            "src/xquant/etf_dividend_accounting.py","src/xquant/etf_valuation_monitor.py","src/xquant/cashflow_research.py",
            "src/xquant/etf_execution_research.py","src/xquant/three_asset_research.py",
            "tests/test_etf_dividend_accounting.py","tests/test_etf_valuation_monitor.py","tests/test_cashflow_research.py",
            "tests/test_three_asset_research.py","tests/test_etf_execution_research.py","tests/test_etf_valuation_collector.py",
            "docs/notes/"+SLUG+"-review.md","research/notebooks/"+SLUG+"-practice.ipynb"]
    independent=ROOT/"scripts/verify_etf_dividend_accounting_independent.py"
    if independent.exists():source.append(str(independent.relative_to(ROOT)))
    members={name:ROOT/name for name in source}
    for p in OUT.rglob("*"):
        if p.is_file() and p.name not in {"reproduction_bundle.zip","delivery_manifest.json"} and not p.name.endswith(".lock"):
            members[str(p.relative_to(ROOT))]=p
    manifest={"members":{name:sha(path) for name,path in members.items()},
              "scope":"frozen accounting inputs/results plus actual first-seen monitor samples; no historical premium backfill",
              "background_installed":False,"live_orders":False}
    (OUT/"delivery_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    with zipfile.ZipFile(OUT/"reproduction_bundle.zip","w",zipfile.ZIP_DEFLATED) as bundle:
        for name,path in members.items():bundle.write(path,name)
        bundle.write(OUT/"delivery_manifest.json","delivery_manifest.json")
    print("Packaged",len(members),"hashed members",flush=True)


def main():
    annotation();figures();attribution();render();notebook();readme();package()


if __name__=="__main__":main()
