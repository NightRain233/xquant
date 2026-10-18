"""Render cash-flow evidence, investment review, notebook, and handoff bundle."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SLUG = "dca-comparison-2026-10-04"
OUT = ROOT/"outputs"/SLUG
LABELS = {"Three":"三组合", "Two":"两组合", "SP500":"标普500人民币代理"}
UV = "uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 --with exchange-calendars==4.13.2"


def table(frame):
    data=frame.fillna("尚未恢复/不适用").astype(str)
    return "| "+" | ".join(map(str,data.columns))+" |\n| "+" | ".join(["---"]*len(data.columns))+" |\n"+"\n".join("| "+" | ".join(map(str,row))+" |" for row in data.to_numpy())


def percent(value):
    return f"{value:.2%}"


def wan(value):
    return f"{value/10000:.2f}"


def main():
    main_frame=pd.read_csv(OUT/"main_summary.csv").set_index("strategy")
    monthly_amount=float(main_frame.principal.iloc[0]/main_frame.contributions.iloc[0])
    validation=json.loads((OUT/"validation.json").read_text())
    cohorts=pd.read_csv(OUT/"cohort_accounts.csv")
    rolling=pd.read_csv(OUT/"rolling_dca_accounts.csv")
    rolling_summary=pd.read_csv(OUT/"rolling_dca_summary.csv")
    unit_events=pd.read_csv(OUT/"unit_drawdown_events.csv")
    sensitivity=pd.read_csv(OUT/"cashflow_sensitivity.csv")
    main_table=[];risk_table=[];recover_table=[];giveback=[]
    for strategy in LABELS:
        s=main_frame.loc[strategy]
        main_table.append({"配置":LABELS[strategy],"累计本金（万元）":wan(s.principal),
                           "期末净退出估值（万元）":wan(s.terminal_liquidation),"净盈利（万元）":wan(s.profit),
                           "盈利/本金":percent(s.profit_on_principal),"历史资金加权XIRR":percent(s.xirr)})
        risk_table.append({"配置":LABELS[strategy],"最大本金亏损（元）":f"{s.worst_loss_amount:,.2f}",
                           "金额发生日":s.worst_loss_amount_date,"当时本金（万元）":wan(s.principal_at_worst_amount),
                           "最深本金亏损比例":percent(s.worst_loss_ratio),"比例发生日":s.worst_loss_ratio_date,
                           "现金流调整净值最大回撤":percent(s.unit_max_drawdown)})
        events=unit_events[(unit_events.strategy==strategy)&(~unit_events.censored)]
        longest=events.loc[events.underwater_calendar_days.idxmax()]
        recover_table.append({"配置":LABELS[strategy],"主账户最长本金亏损段（日历天）":int(s.longest_completed_principal_loss_days),
                              "历史最后一次回到本金日":s.final_observed_breakeven,
                              "收益净值最长回前高（日历天）":int(longest.underwater_calendar_days),
                              "净值回前高区间":f"{longest.peak} → {longest.recovery}"})
        daily=pd.read_csv(OUT/f"account_{strategy}.csv",index_col=0,parse_dates=True)
        decline=daily.profit-daily.profit.cummax()
        trough=decline.idxmin();peak=daily.profit.loc[:trough].idxmax()
        peak_profit=float(daily.profit.loc[peak])
        subsequent=daily.profit.loc[trough:]
        rec=subsequent[subsequent>=peak_profit].index
        giveback.append({"strategy":strategy,"profit_peak":peak,"profit_trough":trough,
                         "worst_profit_giveback":float(decline.min()),"principal_at_trough":float(daily.principal.loc[trough]),
                         "profit_recovery":rec[0] if len(rec) else pd.NaT})
    pd.DataFrame(giveback).to_csv(OUT/"profit_giveback.csv",index=False)
    win_rows=[]
    for months in [12,36,60]:
        matched=rolling[rolling.months==months].pivot(index="start_month",columns="strategy",values="profit_on_principal")
        for first,second in [("Two","Three"),("Two","SP500"),("Three","SP500")]:
            win_rows.append({"months":months,"pair":first+"/"+second,"cohorts":len(matched),
                             "first_higher_terminal_share":float((matched[first]>matched[second]).mean())})
    pd.DataFrame(win_rows).to_csv(OUT/"matched_cohort_comparisons.csv",index=False)
    cohort_risk=[]
    for strategy in LABELS:
        for policy in ["continue","stop_after_12"]:
            group=cohorts[(cohorts.strategy==strategy)&(cohorts.policy==policy)]
            worst_ratio=group.loc[group.worst_loss_ratio.idxmin()]
            worst_amount=group.loc[group.worst_loss_amount.idxmin()]
            longest=group.loc[group.longest_completed_principal_loss_days.idxmax()]
            cohort_risk.append({"strategy":strategy,"policy":policy,"cohorts":len(group),
                                "worst_loss_ratio":worst_ratio.worst_loss_ratio,"worst_ratio_start":worst_ratio.start_month,
                                "worst_ratio_date":worst_ratio.worst_loss_ratio_date,
                                "worst_loss_currency":worst_amount.worst_loss_amount,"worst_amount_start":worst_amount.start_month,
                                "worst_amount_date":worst_amount.worst_loss_amount_date,
                                "longest_completed_principal_loss_days":longest.longest_completed_principal_loss_days,
                                "longest_start_month":longest.start_month,
                                "longest_censored_days":group.longest_censored_principal_loss_days.max()})
    pd.DataFrame(cohort_risk).to_csv(OUT/"cohort_risk_envelope.csv",index=False)
    roll_table=[]
    for months in [12,36,60]:
        for strategy in LABELS:
            row=rolling_summary[(rolling_summary.months==months)&(rolling_summary.strategy==strategy)].iloc[0]
            roll_table.append({"月数":months,"配置":LABELS[strategy],"完整起点数":int(row.cohorts),
                               "中位累计盈利/本金":percent(row.median_profit_ratio),"最差累计盈利/本金":percent(row.worst_profit_ratio),
                               "最差末期盈亏（万元）":wan(row.worst_profit_currency),
                               "最差起点":row.worst_start_month,"期末仍亏损起点占比":percent(row.negative_terminal_share)})
    giveback_table=pd.DataFrame([{"配置":LABELS[r["strategy"]],"最多回吐盈利（万元）":wan(r["worst_profit_giveback"]),
                                 "盈利高点":str(r["profit_peak"].date()),"盈利低点":str(r["profit_trough"].date())} for r in giveback])
    start_years=cohorts[(cohorts.policy=="continue")&cohorts.start_month.str.endswith("-01")]
    year_comparison=start_years.pivot(index="start_month",columns="strategy",values="profit")/10000
    year_comparison=year_comparison[["Three","Two","SP500"]].map(lambda x:f"{x:.2f}").rename(columns=LABELS).reset_index()
    stop_table=[]
    for row in cohort_risk:
        if row["policy"]!="stop_after_12":continue
        stop_table.append({"配置":LABELS[row["strategy"]],"最深本金亏损比例":percent(row["worst_loss_ratio"]),
                           "最大亏损金额（万元）":wan(row["worst_loss_currency"]),
                           "最长已完成本金亏损段（日历天）":int(row["longest_completed_principal_loss_days"]),
                           "最长等待的起点":row["longest_start_month"]})
    units=pd.read_csv(OUT/"unit_q3_q5_metrics.csv").set_index("strategy")
    q5=[]
    for strategy in LABELS:
        s=units.loc[strategy]
        q5.append({"配置":LABELS[strategy],"TWR历史年化":percent(s.cagr),"年化波动":percent(s.volatility),
                   "Sharpe零rf":f"{s.sharpe_zero_rf:.2f}","Sortino零目标":f"{s.sortino_zero_target:.2f}",
                   "Calmar":f"{s.calmar:.2f}","月胜率":percent(s.monthly_win_rate),"最差月":percent(s.worst_month)})
    point=cohorts[(cohorts.policy=="continue")&(cohorts.start_month=="2021-01")]
    recent=cohorts[(cohorts.policy=="continue")&(cohorts.start_month=="2026-01")]
    selected_table=[]
    for subset in [point,recent]:
        for strategy in LABELS:
            s=subset[subset.strategy==strategy].iloc[0]
            selected_table.append({"起点":s.start_month,"配置":LABELS[strategy],"本金（万元）":wan(s.principal),
                                   "末期盈利（万元）":wan(s.profit),"最深本金亏损比例":percent(s.worst_loss_ratio)})
    cny_fx=sensitivity[sensitivity.case=="fx_constant_currency_DIAGNOSTIC"].iloc[0]
    test_path=OUT/"test_results.json"
    test_statement="7项现金流/费用/回本测试通过；逐笔独立账本与解包复验见delivery_verification.json。"
    note_text=f"""# 专业现金流比较：每月定投三组合、两组合与标普500（2026-10-04）

**同样月初每月投入{monthly_amount:,.0f}元人民币，在这段冻结样本里，两组合最终赚得最多；三组合持仓回撤较浅；标普500在不少三年/五年定投窗口里比三组合更赚钱。定投没有消除本金亏损，也没有消除成熟账户回吐大额盈利的风险。** 判断应同时看最终财富、起点敏感性、金额风险、回本等待与未来入金能力，不能只排历史年化。

本轮继续遵循项目策略复核skill，先做耗时评估并复用数据/信号/交易日历，813个独立账户用2个进程计算。仅研究三类定投账户，没有重跑BTC或多资产；它们两项交付缺口仍未处理，不称整体交付完成。

## 研究契约：怎样做到公平

1. 初始本金为0，无额外10万元起始资金。2015年1月至2026年9月每月等额入金，共141笔，合计141万元。三账户到账时点完全相同：每月第一个三只境内ETF都有有效开盘的交易日，上海09:29:59到账。金额可线性缩放，但真实整手、最低佣金会破坏小额线性关系。
2. 三组合为510300/513100/518880；两组合为513100/518880。均固定20个共同交易日简单收益样本波动的倒数权重，每10个共同日发正式信号、下个共同开盘调仓；无杠杆、无趋势退出。复用此前冻结信号相位，各起投账户不重选锚点。第一笔按2014-12-31已可见的20日历史启动；以后新钱按开盘前最新已知目标比例买入。新增资金本身不触发整仓重置，只有正式调仓日才卖旧仓恢复目标。
3. 标普500采用冻结SPY的Yahoo auto_adjust OHLC作为分红再投资研究代理，以冻结USD/CNY换成人民币。月初入金先留人民币现金，等美国自己的下一次开盘才买入，分数份额。**这不是境内标普500ETF的实盘结果**，未包含QDII溢价、申购限制、真实换汇结算、股息预提税、最低佣金或个人税务。SPY的总回报包含再投资假设，见[State Street官方产品说明](https://www.ssga.com/us/en/institutional/etfs/state-street-spdr-sp-500-etf-trust-spy)。境内ETF是TickFlow forward_additive；两类供应商的复权/分红处理不完全同一契约，未完成原始价与现金分红逐笔对照，不把精确差值当生产级总回报证明。
4. **主成本统一为真实交易名义金额每边10bps**（买入、卖出都收费），扣费后目标份额用固定点求解。这区别于前轮native半周转率×10bps，未沿用其偏低费用。标普500只在每月新增资金买入时收费，组合还承担调仓成本。额外测试30bps交易费及SPY换汇25/50bps。现金不计息、即时结算、不模拟整手；未给某个方案免除交易成本。
5. 每个日历日上海15:00:02估值，包括中国休市日，避免漏掉美国/汇率在长假里的风险。国内ETF只沿用此前可知收盘，不伪造可交易报价；SPY只用已完成美国收盘，FX D标签于UTC次日00:00:01可用是**未经供应商核实的研究假设**，另检验延后一日。最后估值在2026-09-30上海下午，SPY最新是9月29日美国收盘，未偷用更晚的9月30日美国收盘。异步收盘仍不等于同时可成交的价格。
6. 期末先给出账户市值，再预扣持仓卖出10bps退出成本，得到“净退出估值”；每日本金亏损也按这一保守口径计算。费用只在实际研究买卖时扣款，每日退出费是估值诊断，不是每天真的卖掉又买入。该估值并非已经发生的券商清算，特别是SPY在上海下午尚不能以此前美股收盘价即时卖出。

## 同一长期起点：最终赚了多少

金额单位万元，期末截至2026-09-30上海下午，全部是该研究口径历史结果。

{table(pd.DataFrame(main_table))}

XIRR按每笔真实日期的负入金、末日净退出估值的正现金流求解，它反映这套实际资金到账顺序的历史资金加权回报；不是把终值/本金直接开11.75次方，也不是未来收益预测。TWR在入金前开盘资产净值发行账户单位，外部入金不制造投资收益。两者回答不同问题：XIRR看这些钱赚了多少，TWR看持仓策略本身的增长。

这一起点两组合比三组合多赚约120.83万元，三组合比标普500多赚约38.86万元。组合累计交易费约6.22/6.38万元，SPY约0.14万元（未计额外换汇与税）；这些费用已经在账户结果里，不能再减第二次。历史后期纳指与黄金上涨、越往后越大的本金，使两组合XIRR高于其TWR；不能把20.84%读成未来定投收益率。样本没有覆盖2000–2002或2008的大熊市，资产池也不是事前注册的样本外选择。

## 账户亏过多少：三种风险必须一起看

**本金亏损**：账户净退出估值减截至该日累计投入本金。下表亏损金额与亏损比例各自取最差日，可能不是同一天，分母是当时投入本金，不是期末141万元。

{table(pd.DataFrame(risk_table))}

2015年起点前期攒下了利润缓冲，所以主账户低于累计本金的金额很小；这不能说明持有中途只会亏几千元。新增本金会降低同一笔亏损占本金的比例，但在价格不变时不会把负的金额盈亏直接变正。纯看总市值的新高更会受入金干扰，所以用现金流调整净值量回撤。

**盈利回吐**：把每天“净账户值−累计本金”的最高值与之后低点比较，主账户还曾经历这些金额下降：

{table(giveback_table)}

这是累计投资盈利从高点回落，已去掉新增本金，包含后来新增资金参与市场的损益；它与单位净值回撤是不同指标。长期账户即便仍高于本金，也可能痛失几十万元利润。两组合在本样本中成熟账户的最大盈利回吐约82.33万元，远大于其早期3847元的本金短缺。

**换起点后的本金风险**：遍历每个月开始并继续投到同一截止日，最深本金亏损比例约三组合−9.08%、两组合−11.11%、标普500−27.64%；三者最大亏损金额的各自包络约−2.08/−0.98/−4.27万元。比例与金额最差来自不同账户、不同持有时长，不能拼成一个不存在的账户；明细在cohort_risk_envelope.csv。两组合最深比例发生在2026年3月刚起投、尚未攒下利润缓冲的账户，历史三年/五年完整窗口当然覆盖不到这个近期起点。

## 多久回本：回到本金和回到前高不同

{table(pd.DataFrame(recover_table))}

“主账户最长本金亏损段”从首次低于累计本金日到再回本金，计日历天；“历史最后一次回到本金日”表示此后截至样本结束未再低于本金，这是**事后观察**，不是当天可知的永久回本承诺。初次触及本金可能再次跌回去；另保存首次连续三个月月底非负和所有完整/未完成亏损段。净值回前高从此前净值高点起算，不受入金直接抬升。即使本金亏损很快修复，单位净值可能等待两三年；标普500更深的最大回撤也不一定有更长的最长历史等待。

每个月重新开始的账户里，三组合最长已完成本金亏损段372天、两组合160天、标普500128天。这些是该全样本继续定投的观察包络，不是未来等待上限；仍未回本的账户保持右删失，绝不填0天。完整本金亏损段和单位净值回撤段分别保存，不能混用两个定义。

## 公平的三年/五年定投：不固定在2015这个起点

逐月起投，固定连续投入12/36/60笔，分别有130/106/82个完整起点；每个起点三账户入金一模一样。36笔累计本金36万元、60笔60万元，末日为最后投入月份的月末，最后一笔钱并没有持有三/五年。完整固定时长窗口共954个，高度重叠，不把亏损频率当未来概率。

{table(pd.DataFrame(roll_table))}

三年定投中，三组合最差起点是2019年11月，2022年10月底净退出估值约35.96万元，本金36万元，亏445.80元；两组合最差仍赚2.83万元；标普500最差仍赚1.33万元。**前轮单笔投入三年全正收益，不能推出逐月定投三年也全正收益。** 定投是一串不同入场价与持有期，后期新本金往往尚未经历足够恢复时间。

三年累计盈利/本金的中位数分别22.36%/30.89%/25.47%；五年45.01%/59.07%/48.08%。三组合五年最差盈利略高于标普500，但其中位数更低，说明“回撤较浅”与“总财富一定更多”不能划等号。

在逐个同起点、同本金、同截止日配对后，两组合三年胜过标普50063.21%的历史窗口，五年92.68%；三组合胜过标普500仅35.85%/48.78%。这些是重叠样本描述，非统计独立的胜率或预测。两组合没有每次都赢，三组合也不能凭2015起点的终值宣称全面优于标普500。

## 如果未来无法继续每月投入

另建130个完整“只投12个月，之后停止追加但继续持有/正式调仓”的起点，每个起点各投入12万元。它测试现金流持续性，不是退休提款测试，也不是给停止投入者补现金。

{table(pd.DataFrame(stop_table))}

三组合最长本金等待从继续投账户包络372天延长到停缴账户包络430天；例如2021年中开始，后续停止追加后，2022年下跌使本金亏损持续更久。两组合和标普500也继续承受市场风险。表中各项是各自最差账户，并非都发生在同一个起点；不同政策本金总量不同，不能拿继续投的141万元账户总额与只投12万元的账户总额直接判优劣。

若2015年开始只投12个月，末日净退出估值约三组合61.46万元、两组合83.26万元、标普50057.43万元；这些长期高利润不能替代对不同停缴年份的检查。现金流不断的假设本身，是定投计划的重要条件。

## 较近的实际起点

{table(pd.DataFrame(selected_table))}

2026年只观察到9个月，不年化短期资金回报。更换起点后，2026年标普500盈利高于三组合，证明2015长期终值排名不能直接套用任何新投资者。完整每年1月起投的末期盈利（万元）如下，不同年份本金/持有长度不同，只在同一行横向比较：

{table(year_comparison)}

## 收益净值、年度月度与参数稳定性

{table(pd.DataFrame(q5))}

年度账户表列年初市值、当年入金、市场损益、交易费、年末市值和收益净值回报，月度表同样剔除外部资金；不能把“年末市值比年初高”当投资收益。累计账户盈亏以每年/每月实际资金守恒复算。benchmark_alpha.csv只是异步日标签收益对人民币SPY的零rf回归描述，不用于宣称预测alpha或因果优越。

月初/15日后首个交易日/月末三种入金日期下，长期末期排名均为两组合、三组合、SPY，金额有所变化；不是挑最赚钱的缴款日。10/40/60日波动窗口只解释局部稳定性，不替换固定20日。成本升到实际每边30bps，三/两组合期末约381.96/499.51万元，SPY365.02万元；组合交易成本敏感性明显更高。SPY另加双向换汇50bps，期末约362.84万元、XIRR约15.14%，本轮长窗口排名未变；真实跨境税费/工具差异仍需另审。

FX额外滞后一日的结果约366.45万元，未改变本轮长期结论；人为固定汇率的诊断末期约{wan(cny_fx.terminal_liquidation)}万元，但初期最深本金亏损约{percent(cny_fx.worst_loss_ratio)}，与主结果不同。这说明汇率能改变风险路径，**固定汇率不是可买到的无成本对冲产品**。股息税和国内ETF复权差异未由这些敏感性消除。

## 投资判断与未来限制

从该样本资金流结果看，两组合是增长候选，三组合是更浅持仓回撤的候选，标普500是低换手、实现简单的重要基准。三者没有一个在所有指标占优：两组合依赖纳指与黄金行情，三组合增加A股暴露与调仓开销，标普500承受更深股票下跌，但历史上不少固定时长定投窗口的终值高于三组合。

未来若纳指与黄金同步长期下跌，两组合的历史优势可能消失；若A股独立上涨，三组合可能反超；若股票深跌且收入同时下降，定投追加与回本体验都会恶化。黄金本身有价格风险，纳指ETF也有溢价风险，见[华安黄金基金原始风险说明](https://www.huaan.com.cn/upload2010/2013/06/21/082816905_0_b7ca7b32-4cab-30a2-879c-37d153eefc3a.pdf)及[国泰纳指ETF官方风险公告](https://st.gtfund.com/report/2025/04/34b9b9ea1bfbff560811cc81b5f0faf7cdbe45ec/国泰基金管理有限公司关于纳斯达克100交易型开放式指数证券投资基金二级市场交易价格溢价风险提示公告.pdf)。定投是规律现金流方法，见[Investor.gov定义](https://www.investor.gov/introduction-investing/investing-basics/glossary/dollar-cost-averaging)，不能把历史本金回本速度变成收益保证。

这份报告支持把两组合、三组合与标普500放在相同未来现金流下继续观察。它不支持按20.84%/16.85%/15.30%来规划未来财富，也不支持把“历史最差五年全赚钱”写成保本承诺。下一步应固定20日规则，做前瞻记账，并按实际可购买的标普500载体补充原始价/分红、溢价、税费、整手与成交约束。

## 复核与交付

冻结行情5/5哈希匹配，4287个日历估值时点、141个月度现金流，813个独立账户、954个固定期限窗口。主账户同额同日现金流已核对；原始入金/份额/买卖费用/每日资产/P&L有守恒检查，最大主账户残差约{validation['max_main_account_residual']:.2g}元。时钟表保留资金到账、美国开盘、FX可得时刻和每日已知收盘，不靠只看日期标签证明因果顺序。主线计算后Luna只读复算本金、终值、亏损、单位数和时钟，未发现数值异议。

{test_statement} 通过这些检查只支持本研究现金流账本的内部一致性，不证明供应商价格口径、真实换汇结算或券商执行。实测数据准备约0.5秒，单个全期三/两组合约0.09秒，SPY约0.01秒；2进程独立账户部分约23秒，全流程约{validation['elapsed_seconds']:.1f}秒。未重新下载行情。

[完整输出README](../../outputs/{SLUG}/README.md)、[账户与起点图](../../outputs/{SLUG}/account_comparison.png)、[固定期限起点图](../../outputs/{SLUG}/cohort_comparison.png)、[practice notebook](../../research/notebooks/{SLUG}-practice.ipynb)。CSV保留完整精度，表格只做阅读四舍五入；完整冻结数据、日历/信号输入、源码、测试与本报告随reproduction_bundle.zip移交。
"""
    note=ROOT/"docs/notes"/f"{SLUG}-review.md"
    note.parent.mkdir(parents=True,exist_ok=True);note.write_text(note_text)
    readme=f"""# 每月等额定投账户比较

完整投资报告：[review](../../docs/notes/{SLUG}-review.md)。三/两组合固定20日逆波动，标普500为SPY人民币研究代理。

原仓库运行：

```sh
{UV} python scripts/review_dca_accounts.py --preflight-only
{UV} python scripts/review_dca_accounts.py --workers 2 --monthly {monthly_amount:g}
PYTHONPATH=src {UV} python -m pytest tests/test_cashflow_research.py -q
{UV} python scripts/render_dca_review.py
{UV} python scripts/verify_dca_delivery.py
```

空目录解压reproduction_bundle.zip后：

```sh
{UV} python scripts/review_dca_accounts.py --snapshot inputs/market_data --reference inputs/reference --workers 2
PYTHONPATH=src {UV} python -m pytest tests/test_cashflow_research.py -q
{UV} python scripts/render_dca_review.py
{UV} python scripts/verify_dca_delivery.py --ledger-only
```

包内五份行情、原覆盖表、冻结三资产信号目标和估值日期完整，不依赖BTC/multi旧结果。main_summary是主账户结果；account_*是净值/本金/单位净值/费用每日账本；fills_*中valuation_index是成交首次被日估值包含的位置（SPY实际时点查contribution_clock），不是US真实成交日期标签。SPY execution_price_cny是已知FX折算报价，非真实换汇成交。terminal_liquidation和profit是末日已知收盘预扣退出费的估值代理，不是已执行的卖出。

principal_loss_events回答何时低于累计本金；unit_drawdown_events回答扣除外部资金后的回前高；profit_giveback回答累计净盈利最多回吐多少钱。cohort_accounts遍历141起点继续投及130起点投12个月后停缴；rolling_dca_accounts遍历12/36/60期定投；matched_cohort_comparisons逐起点公平比终值。cashflow_sensitivity记录入金日期、真实交易费、汇率费用/时钟与波动窗口形状，未选最优参数。

main命令会并行两进程独立账户并显示进度，所有来源/产物SHA和环境版本在manifest。verify脚本独立逐笔重建三账户并解包重算CSV；ledger-only只做哈希、时钟、逐笔账本。时间耗时和ZIP时间戳可以不同，不要求整个ZIP字节一致。当前脚本绘图缓存不属于交付。

全日历估值包括中国假期；国内ETF估值报价可能陈旧，valuation_quotes逐日保存三个国内报价日期与SPY/FX已知时钟。每日15:00:02时点只有此前美股收盘，不含当天晚些时候美股价格；FX bar截止时刻仍是研究假设。国内forward_additive与SPY auto_adjust未完成逐笔现金分红统一，税务/真实基金载体尚未验证，勿把结果当券商可得收益。
"""
    (OUT/"README.md").write_text(readme)
    cells=[]
    def md(value):cells.append({"cell_type":"markdown","metadata":{},"source":value.splitlines(keepends=True)})
    def code(value,output=None,tags=None):cells.append({"cell_type":"code","metadata":{"tags":tags or []},"execution_count":None,"source":value.splitlines(keepends=True),"outputs":output or []})
    md("# 三组合、两组合与标普500：相同现金流定投\n"+note_text.split("## 研究契约")[0].split("\n",2)[2])
    code("from pathlib import Path\nimport pandas as pd\nROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src/xquant').exists())\nOUT = ROOT / 'outputs/dca-comparison-2026-10-04'\n",tags=["repository-root-bootstrap"])
    md("## 数据和基线\n月初人民币1万元，0初始资金；交易费实际每边10bps，三/两组合20日逆波动，SPY美元复权价格按已知FX换算。先按README执行完整复算，再读取表格。不联网下载。")
    for title,files in [("主账户盈亏与回本",["main_summary.csv","principal_loss_events.csv","unit_drawdown_events.csv","profit_giveback.csv"]),
                        ("Q3/Q5与年度月度",["unit_q3_q5_metrics.csv","annual_accounts.csv","monthly_accounts.csv","benchmark_alpha.csv"]),
                        ("不同起点与固定期限",["rolling_dca_summary.csv","cohort_risk_envelope.csv","matched_cohort_comparisons.csv"]),
                        ("停止入金及敏感性",["cashflow_sensitivity.csv"]),
                        ("时钟审计",["contribution_clock.csv","valuation_quotes.csv"])]:
        md("## "+title)
        for file in files:code(f"display(pd.read_csv(OUT / '{file}'))\n")
    for file in ["account_comparison.png","cohort_comparison.png"]:
        code("from IPython.display import Image, display\n"+f"display(Image(filename=str(OUT / '{file}')))\n",
             output=[{"output_type":"display_data","metadata":{},"data":{"image/png":base64.b64encode((OUT/file).read_bytes()).decode()}}])
    md("## 通俗结论\n"+note_text.split("## 投资判断与未来限制\n\n")[1].split("## 复核与交付")[0])
    for i,cell in enumerate(cells):cell["id"]=f"dca-{i:03d}"
    notebook=ROOT/"research/notebooks"/f"{SLUG}-practice.ipynb"
    notebook.parent.mkdir(parents=True,exist_ok=True)
    notebook.write_text(json.dumps({"cells":cells,"metadata":{"kernelspec":{"name":"python3","language":"python","display_name":"Python 3"}},"nbformat":4,"nbformat_minor":5},ensure_ascii=False,indent=1))
    manifest=json.loads((OUT/"manifest.json").read_text())
    manifest["source"]["scripts/render_dca_review.py"]=""
    verifier=ROOT/"scripts/verify_dca_delivery.py"
    if verifier.exists():manifest["source"]["scripts/verify_dca_delivery.py"]=""
    for name in manifest["source"]:manifest["source"][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    archive=OUT/"reproduction_bundle.zip"
    additions={str(path.relative_to(ROOT)):path.read_bytes() for path in [note,notebook,OUT/"README.md",*[ROOT/name for name in manifest["source"]]]}
    with zipfile.ZipFile(archive) as z:members={name:z.read(name) for name in z.namelist() if name not in additions}
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        for name,data in {**members,**additions}.items():z.writestr(name,data)
    manifest["bundle_members"]={name:hashlib.sha256(data).hexdigest() for name,data in {**members,**additions}.items()}
    manifest["outputs"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!="manifest.json"}
    manifest["reports"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [note,notebook]}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(note)


if __name__=="__main__":main()
