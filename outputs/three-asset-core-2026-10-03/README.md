# 纯三组合研究复现

入口：[完整研究报告](../../docs/notes/three-asset-core-2026-10-03-review.md)。只涉及510300/513100/518880；BTC/multi交付遗留未修复。

在仓库根目录运行（Python3.12或兼容版本；实际版本见manifest）：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python scripts/review_three_asset_core.py --benchmark-only
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python scripts/review_three_asset_core.py
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python -m pytest tests/test_three_asset_research.py -q
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python scripts/render_three_asset_review.py
```

默认输入为旧 `outputs/strategy-healthcheck-2026-10-02/market_data/` 三份Parquet与 `next_open/` 中NAV/成交/配置。现有文件不能用重新下载替代。reproduction_bundle.zip内已包含这六份输入、新核、计算脚本、渲染脚本、测试和项目依赖文件；**该zip不依赖BTC或旧multi gzip。** 它可重算本研究，所附原实现源码仅作溯源，不声称自包含重跑原trading生产账本。

在空目录解压复现包后运行：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python scripts/review_three_asset_core.py --snapshot inputs/market_data --reference inputs/reference
PYTHONPATH=src uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python -m pytest tests/test_three_asset_research.py -q
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python scripts/render_three_asset_review.py
```

计算脚本会逐行核对旧NAV与成交，任何超出1e-5的差异都会失败。包外原coverage表存在时额外验证SHA；移交时请先按manifest校验zip和输入，解包后的输入路径改变不影响其字节哈希。渲染脚本需先运行计算脚本。统计无随机抽样，时间记录和zip时间戳会变化；比较CSV数值而非要求整个zip字节一致。

主要文件：summary/annual/monthly、attribution、weights_summary、risk_contribution、benchmark_alpha、rolling_worst及逐窗口rolling文件、drawdown_events、entry_recovery文件、historical_stress、subperiods、hypothetical_shocks、hypothetical_five_year、comparison.png。daily的资产列是金额P&L，非收益率；trades的group_cost重复记在同一组每个资产行，不可直接跨资产求和。日cost列及原commission聚合才是总费用。

全部主表采用native半周转率费用；gross10bps是单独的实际双边收费对照。固定全样本平均权重标DIAGNOSTIC，不能列为事前公平方案。最新权重是收盘实际持仓，区别于上次信号目标。未来情景不含概率，不是预测。

manifest记录输入/源码/产物SHA与环境。报告与notebook由render脚本生成并补入manifest。原研究说明的两项multi交付缺口仍然存在。
