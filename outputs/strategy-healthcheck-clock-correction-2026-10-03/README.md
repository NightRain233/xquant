# Strategy health check clock correction — 2026-10-03

本目录保存跨市场可用时点修正后的**异步研究模型**输出。它不是原生产契约的修复，也不是券商成交、换汇或结算验证。旧绩效与新模型在执行时序、成交组和现金预算上不同，数值差异不能单独解释为删除未来数据的影响。

## 新的研究执行契约

- **BTC 信号**：UTC 日标签为 D 的 BTC 日线在上海 D+1 08:00 才完整。信号须等所有所需 D 标签行情都完整后 1 秒才可用。
- **BTC 与 ETF 分开成交**：信号可用后，ETF 在之后首个 XSHG 收盘成交；BTC 在之后首个 UTC 日线收盘成交。不同市场按真实先后时间分别成交，不能使用同标签 BTC 收盘回填更早的 A 股成交数量。
- **多资产分市场开盘**：月末信号待相关日线完整后才可用；每项资产在信号可用后的首个本市场开盘分别成交。只允许已实际完成的卖出款资助后续买入。现金不足时按比例缩小买单，本轮不自动重试，等待下一正式信号。
- **共同账务约定**：模型使用分数份额、单一现金账户和即时结算。这是研究账本假设，不代表跨市场资金真实可及时划转，也没有模拟券商手数、换汇成交或结算周期。多资产与 FX 结果不能称为实盘执行通过；测试通过也不能证明所有时序风险均已排除。
- **FX 记账代理**：模型假设 UTC 日标签为 D 的 FX bar 于 D+1 00:00:01 已完整；在每项美元资产 bar 开盘前，取当时最近一笔已完整的 FX 收盘价，并以该常数乘过同一根 bar 的 OHLC。供应商 FX bar 的实际结束时刻尚未独立核实，所以该可用时钟只是研究模型假设。它是滞后会计代理，不是可成交的真实换汇价格；不会把不同时间的 FX 高低价乘成同步人民币区间。真实换汇成交、跨账户划款和结算均未模拟。
- **旧全球 RS**：报告复用旧输出作为历史参考，明确标记为未复核，且排除在修正版候选资格门槛之外。

BTC 参数维持冻结值：10 个 XSHG 交易日节奏、ST(10/SMA/3)、真实 1% 再平衡阈值、无 15 个百分点单资产交易限制、BTC 开关切换强制执行。每边基础费用 20 bps、滑点 10 bps；额外成本敏感性为 10/20 bps。多资产保持既定资产池、资格规则、参数网格和门槛，不以调参修正时序。

## 输入与复现

性能实测：开启分析的单个模拟耗时约20秒，约一半用于时钟与日历查询。本机2个物理核心；后续先复用行情和时钟，再以2个进程分批计算独立候选，并保存结果、显示进度。先测小样本耗时，避免直接启动无进度的串行全量任务。uv只负责运行环境，不自动并行化回测。

复用原体检的 83 份行情 parquet 及其 SHA256，不重新下载。原始快照位于 `../strategy-healthcheck-2026-10-02/market_data/`。需要让其他 agent 独立复核时，需同时提供该 `market_data/`、本轮 finalize 生成的 `source_bundle.zip`、`manifest.json`，以及源包中固定的策略配置和资产池配置；仅给 CSV 或压缩结果不足以重建输入。

从 `xquant/` 目录运行。当前规范输出中的 `btc/` 已存在，runner 使用 `exist_ok=False`，因此不要在本目录重复运行 BTC family。BTC 命令仅用于目标 `btc/` 尚不存在的干净输出根：

```bash
PY=../trading/backend/.venv/bin/python
SNAP=outputs/strategy-healthcheck-2026-10-02/market_data
OUT=outputs/strategy-healthcheck-clock-correction-2026-10-03

# 仅当目标输出根下的 btc/ 不存在时运行；当前规范输出已有 btc/。
$PY scripts/review_cross_market_clock.py --snapshot "$SNAP" --output "$OUT" --family btc
```

multi family 写入 `$OUT/multi_asset_full.json.gz` 和 Markdown 报告，不创建独立子目录。本轮 multi 已完成。以下命令用于独立工作副本的干净输出；请勿覆盖本轮归档结果。压缩 JSON 可读取后执行 finalize：

```bash
$PY scripts/review_cross_market_clock.py --snapshot "$SNAP" --output "$OUT" --family multi
$PY scripts/finalize_clock_correction.py
```

`finalize_clock_correction.py` 针对上述规范输出路径生成 Q3 相关性、汇总报告、manifest 与 source bundle。完成后的 [修正报告](../../docs/notes/strategy-healthcheck-clock-correction-2026-10-03-review.md) 汇报 BTC、多资产和测试结果；本 notebook 只读取保存产物。

## 文件说明

- `btc/`：BTC 0/5/7.5/10 与现金参照的异步成交结果、逐组 fills/audit、年度/月度/滚动收益、成本和滞后 FX 诊断。
- `multi_asset_full.json.gz`：异步多资产模型完整结构化结果；文件出现且可解压后才算完成。Notebook 只展示 recommendation、coverage、stability 与小型候选摘要。
- `btc_correlations.csv`：严格截至 2026-09-30 的 Q3 相关性（64 个美国交易日收益），不含 10 月 1 日。
- `manifest.json` 与 `source_bundle.zip`：由 finalize 生成的冻结输入、源码、依赖及交付物哈希和源码包。
- `../strategy-healthcheck-2026-10-02/`：原行情和旧同日标签模型结果；仅用于对照，不覆盖。
