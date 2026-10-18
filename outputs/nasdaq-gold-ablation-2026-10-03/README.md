# 纳指/黄金资产池对照复现

完整报告：[研究note](../../docs/notes/nasdaq-gold-ablation-2026-10-03-review.md)。先阅读原三组合报告理解费用与数据限制。

仓库根目录运行：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python scripts/review_nasdaq_gold.py
```

解压reproduction_bundle.zip到空目录后运行：

```sh
uv run --no-project --with pandas==3.0.3 --with numpy==2.4.6 --with pyarrow==23.0.1 --with matplotlib==3.11.0 --with pytest==9.0.2 python scripts/review_nasdaq_gold.py --snapshot inputs/market_data --reference inputs/reference
```

完整输入均在包内，reference包含前轮manifest、targets_IV20、nav_all。参数敏感性只解释形状，无选择最优。summary与rolling_worst是主表；annual/monthly/subperiods解释样本时期，drawdown_events保存完整回本及未回本事件。hypothetical_shocks是人为情景，不是预测。manifest记录输入/源码/产物SHA和环境。notebook可读取已保存CSV，无需重新下载行情。native和gross10bps费用不得混用。
