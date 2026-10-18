"""Save corrected diagnostics, review note, reproducibility bundle and hashes."""
from datetime import datetime, timezone
import gzip
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import zipfile
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/strategy-healthcheck-clock-correction-2026-10-03'
OLD=ROOT/'outputs/strategy-healthcheck-2026-10-02'
NOTE=ROOT/'docs/notes/strategy-healthcheck-clock-correction-2026-10-03-review.md'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def table(df,columns):
    lines=['| '+' | '.join(title for key,title,fmt in columns)+' |','|'+'|'.join('---' for _ in columns)+'|']
    for _,row in df.iterrows():
        lines.append('| '+' | '.join('—' if pd.isna(row[key]) else f'{row[key]:.2%}' if fmt=='%' else str(row[key]) for key,title,fmt in columns)+' |')
    return '\n'.join(lines)


def diagnostics():
    series={s:pd.read_parquet(OLD/'market_data'/f'{s}.parquet').Close for s in ['BTC-USD','QQQ','SPY','GLD']}
    aligned=pd.DataFrame({s:c.reindex(series['QQQ'].index) for s,c in series.items()}).dropna().pct_change(fill_method=None).dropna()
    rows=[]
    for period,start,end in [('recent_3m','2026-06-30','2026-09-30'),('2026_ytd','2025-12-31','2026-09-30'),('since_2020','2019-12-31','2026-09-30')]:
        sample=aligned[(aligned.index>pd.Timestamp(start)) & (aligned.index<=pd.Timestamp(end))]
        for s in ['QQQ','SPY','GLD']:rows.append({'period':period,'pair':'BTC-USD/'+s,'observations':len(sample),'return_correlation':sample['BTC-USD'].corr(sample[s]),'end':end})
    pd.DataFrame(rows).to_csv(OUT/'btc_correlations.csv',index=False)
    annual=[];monthly=[];stats=[];rolling=[]
    for path in (OUT/'btc').glob('nav_*.csv'):
        nav=pd.read_csv(path,index_col=0,parse_dates=True).nav;returns=nav.pct_change().fillna(0);label=path.stem[4:]
        for year,values in returns.groupby(returns.index.year):annual.append({'strategy':label,'year':year,'return':float((1+values).prod()-1),'partial_year':year in [nav.index[0].year,nav.index[-1].year]})
        month=returns.resample('ME').apply(lambda x:(1+x).prod()-1)
        monthly.extend({'strategy':label,'month':str(d.date()),'return':v} for d,v in month.items())
        stats.append({'strategy':label,'monthly_win_rate':float((month>0).mean()),'worst_month':float(month.min()),'mean_cash_weight':float(pd.read_csv(path).cash_weight.mean())})
        for years in [3,5]:
            ends=nav.index[nav.index>=nav.index[0]+pd.DateOffset(years=years)];positions=nav.index.searchsorted(ends-pd.DateOffset(years=years),side='right')-1
            values=nav.loc[ends].to_numpy()/nav.iloc[positions].to_numpy()-1
            rolling.append({'strategy':label,'years':years,'windows':len(ends),'worst_total_return':float(values.min())})
    for filename,rows in [('annual_returns',annual),('monthly_returns',monthly),('monthly_stats',stats),('rolling_3y_5y',rolling)]:pd.DataFrame(rows).to_csv(OUT/'btc'/f'{filename}.csv',index=False)


def review():
    btc=pd.read_csv(OUT/'btc/summary.csv')
    with gzip.open(OUT/'multi_asset_full.json.gz','rt') as stream:multi=json.load(stream)
    recommendation=multi['recommendation']
    cols=[('strategy','策略','s'),('cagr','年化收益','%'),('max_drawdown','最大回撤','%')]
    short=[('strategy','策略','s'),('return','Q3收益','%'),('max_drawdown','Q3回撤','%')]
    notable=[]
    for row in multi['variants']+multi['benchmarks']:
        if row['id'] in [recommendation.get('candidateId'),'static_stock_bond_gold_cny']:
            notable.append({'strategy':row['id'],'cagr':row['summary']['cagrPct']/100,'max_drawdown':-row['summary']['maxDrawdownPct']/100})
    note=f'''# 策略体检时序修正：2026-10-03

## 更正与结论范围

[独立复核](strategy-healthcheck-2026-10-02-independent-review.md)指出的四项问题成立。原BTC绩效增益、多资产机器判定不能作为已经消除跨市场未来价格影响的结果；此前把单市场时点/账本测试通过扩大为整体执行有效，是过度判断。原报告已添加更正提示、原文另行逐字节归档，原NAV与独立反例未覆盖。

本轮不改MA、ST、资产池、权重上限或门槛，使用同83份冻结行情，另建输出、独立执行模型。**这是明确可知时间的研究模型，不是生产契约修复或真实券商执行证明。** 各市场的时钟、调仓判断时刻、分阶段预算和现金不足处理，均与旧同时成交模型存在实质差异；绩效差值不能全部解释为“仅删除未来数据”。

纯三资产核心、C/LVT和native ST/Bull的本轮旧结果没有被这两项反例推翻；它们的其他投资载体、价格、样本范围限制仍然存在。你此前问的纯核心9月−1.78%、Q3−0.20%、年内+6.77%不依赖BTC UTC或美股直接成交模型，暂可保留为该研究口径结果。

## 修正执行规则

BTC的D标签UTC日线在上海D+1日08:00完成。正式信号等所有所需D标签bar完成后一秒才可用。国内ETF在此后首个XSHG收盘成交，BTC在此后首个UTC日线收盘成交。周末可能BTC先成交，交易日通常ETF先成交。每次只给当前成交组使用当前报价；其他仓位只能按此前已完成收盘估值。

BTC仍用冻结美元信号、10个XSHG日调仓、ST10/SMA/3、实际1%阈值、无15个百分点单资产限制、BTC开关切换强制执行。阈值在信号可用时根据已知持仓估值判断；每边20bps费用+10bps滑点按30bps名义成本计，成本敏感性额外10/20bps。C的2%半周转率阈值和15pp限制没有套到BTC。

多资产月末信号在相关bar全完成后才可用，各标的在此后自己市场首个开盘成交；顺序由UTC时间而非同日标签决定。美国交易日历包含夏令时与提前收盘。没有“共同日期的所有开盘同时发生”或“跨市场先全卖后全买”。每组成交预算按当时全部已知价格与现金计算，只有先前已经发生的卖出款能支持买入。

两组都是分数份额、统一现金账户、即时结算的理想化模型；并未模拟真实USD/CNY换汇、跨券商转账或T+1结算。现金不足的买入按可用现金缩小，不自动重试，等下一次正式信号；因此目标权重、实际持仓和闲置现金可能不同。逐组fills/clockAudit保存现金、NAV、数量重建误差和未满足的目标金额，不能把更浅回撤误读为同样风险敞口下的纯提升。

FX可用时间采用研究假设：FX日标签D于UTC D+1日00:00:01完整，尚未独立核实供应商的FX bar截止时刻。FX敏感性使用**在这一假设下，各美元资产bar开盘前已经完成的FX收盘**，同一bar的OHLC乘同一已知常数；不用不同时间的FX高低价相乘。它是滞后汇率会计代理，不能证明该历史汇率在成交时可实际换汇。BTC人民币估值诊断保持美元信号，使用相同已知FX口径。

BTC每日NAV标在XSHG收盘后两秒，最后为上海9月30日15:00:02，不能包含当天更晚的BTC UTC收盘。多资产每日NAV标在该日标签所有市场bar完成后两秒（含BTC时通常上海次日08:00:02）。两组估值时点不同，不跨组直接排名。

## BTC修正版结果

共同窗口2016-06-07至2026-09-30；全历史年化和回撤如下。数值仅对应上述研究模型。

{table(btc[btc.period.eq('full_common')],cols)}

{table(btc[btc.period.eq('recent_3m')],short)}

新的BTC7.5模型仍显示长期收益增益，但这不恢复“原契约充分验证”的评级，也不构成扩仓依据。BTC0同日程是公平参照；固定现金参照用于检查闲置资金影响。美元代理、跨资产异步调仓、滞后FX、没有真实投资载体与完整样本外证明，仍限制结论。完整月度、年度、滚动3/5年、成本敏感性和FX诊断在btc目录。

严格Q3相关性已重算为64个美国交易日收益，BTC对QQQ/SPY/GLD为0.367474/0.376315/0.520920。这里仍是不同收盘时间的日标签统计，不能称同步相关性。原65个样本混入10月1日的表已保留为旧产物，不继续采用。

## 多资产修正版结果

96组策略参数、85个静态权重邻域重新计算，收益/回撤、年度、滚动3/5年、压力时段、成本与汇率敏感性及原资格门槛均保留。最新研究机器判定为 **{recommendation['status']}**：{recommendation['reason']}

{table(pd.DataFrame(notable),cols)}

此判定属于修正版上述时序/现金/滞后FX模型；不能称已完成真实跨市场换汇、资金结算、样本外或生产验证。旧全球RS完整结果仅作为标注UNREVIEWED的历史参考复用，没有参与候选资格门槛；不宣称它也完成了时序修正。旧资产贡献公式假设同时成交，本轮停用，保留未计算状态，不用它解释异步成交收益。

## 验证与复现

性能记录：单个静态组合在开启性能分析时耗时20.28秒，约一半时间用于交易时钟和日历查询。该测量含分析开销，且当时另有回测运行，不代表固定耗时。本机2个物理核心；后续先复用行情、交易日历和时钟，再用2个进程计算独立候选，保存分批结果并显示进度，避免无进度的串行全量重跑。uv用于管理运行环境，并不自动并行化回测。

新增回归测试直接覆盖晚到BTC不能改变早ETF数量、晚开美股不能改变上午A股订单或预支卖出款、月度实际编排的因果顺序、BTC完成后下一UTC收盘、美国夏令时/半日收盘、FXbar可得性以及成本/现金守恒。测试日志和执行命令在独立输出目录，不能把通过这些用例扩大为排除所有未来数据或现实成交问题。

数据、配置、依赖源码、Python/包版本及所有交付产物的哈希在manifest.json，源码另打包source_bundle.zip。原83份行情未重新下载，逐文件哈希与前次覆盖表核对一致；行情文件仍在原market_data目录且被Git忽略，给其他agent独立重跑必须同时提供它们。

复现入口：[输出README](../../outputs/strategy-healthcheck-clock-correction-2026-10-03/README.md)、[展示notebook](../../research/notebooks/strategy-healthcheck-clock-correction-2026-10-03-practice.ipynb)。建议下一位agent首先重做本次因果反例，再审阅异步执行规则和资金/FX假设，最后核对NAV；不能只复算保存曲线就判定整个模型通过。
'''
    NOTE.parent.mkdir(parents=True,exist_ok=True)
    NOTE.write_text(note)


def freeze():
    files=[ROOT/'scripts/review_cross_market_clock.py',ROOT/'scripts/review_frozen_strategies.py',ROOT/'scripts/finalize_clock_correction.py',ROOT/'scripts/verify_clock_correction.py',ROOT/'src/xquant/research_execution_clock.py',ROOT/'tests/test_cross_market_execution_clock.py']
    files+=list((ROOT.parent/'trading/backend/portfolio_strategies').glob('*.py'))
    files+=list((ROOT.parent/'trading/backend/portfolio_strategies/fixtures').glob('*.json'))
    files+=[ROOT.parent/'trading/scripts/research_multi_asset_balanced_portfolio.py',ROOT.parent/'trading/backend/universes/multi_asset_balanced.json',ROOT.parent/'trading/backend/universes/a_share_etf_core.json']
    files=[p for p in files if p.exists()]
    with zipfile.ZipFile(OUT/'source_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT.parent))
    data={str(p.relative_to(ROOT.parent)):sha(p) for p in (OLD/'market_data').glob('*.parquet')}
    previous=pd.read_csv(OLD/'data_coverage_and_revisions.csv')
    assert len(data)==83 and all(sha(OLD/'market_data'/f'{r.symbol}.parquet')==r.sha256 for r in previous.itertuples())
    manifest={'status':'CORRECTED_RESEARCH_MODEL_NOT_PRODUCTION_OR_BROKER_VALIDATION','created_utc':datetime.now(timezone.utc).isoformat(),
      'python':sys.version,'packages':{name:importlib.metadata.version(name) for name in ['pandas','numpy','pyarrow','exchange_calendars','pytest']},
      'inputs':data,'sources':{str(p.relative_to(ROOT.parent)):sha(p) for p in files},
      'reference_result_sha256':sha(OLD/'multi_asset_full.json.gz'),'original_report_sha256':sha(OLD/'review-original-before-clock-correction.md'),
      'outputs':{str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json' and 'cache' not in p.parts},
      'note_sha256':sha(NOTE)}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--note',type=Path,default=NOTE)
    args=parser.parse_args()
    OUT=args.output; NOTE=args.note
    diagnostics();review();freeze()
