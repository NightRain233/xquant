# XQuant：普通人能拿得住的 ETF 配置研究

用 10～55 年真实历史数据检验：普通人**怎么配能拿得住？哪些热门招数是智商税？**  
本项目仅为历史数据研究记录，不预测涨跌，不构成投资建议。

## 已验证的 5 套好方案与历史表现

| 适用场景 | 推荐方案 | 年化收益 *(vs 死拿)* | 最惨跌幅 *(vs 死拿)* | 详情 |
|---|---|---:|---:|---|
| **国内主力仓** | **逆波动三组合**（沪深 300 + 纳指 + 黄金，两周调） | **~15%\*** *(vs 14.3%)* | **-13.2%** *(vs -29.7%)* | [三组合指南](docs/strategies/two-three-asset.md) |
| **纯美股防大跌** | **标普趋势防守 + 现金**（不碰黄金，年动 2～3 次） | **8.5%** *(vs 8.4%)* | **-16.9%** *(vs -55.2%)* | [标普增强指南](docs/strategies/sp500-enhance.md) |
| **独立黄金账户** | **控波动 + 30 周半仓底线**（年动 4～6 次） | **8.8%** *(vs 9.3%)* | **-34.8%** *(vs -45.6%)* | [黄金增强指南](docs/strategies/gold-enhance.md) |
| **独立比特币** | **趋势 + 150 日均线防抖三档**（走强满仓、转弱空仓） | **69.3%** *(vs 66.6%)* | **-55.5%** *(vs -83.4%)* | [BTC 专题复盘](docs/notes/btc-ashare-buffered-mtf3-2026-11-23-review.md) |
| **美股 / 币圈省心** | **75% 标普 + 25% 黄金**（每季度调一次） | **11.3%** *(vs 10.9%)* | **-41.5%** *(vs -55.2%)* | [标普增强指南](docs/strategies/sp500-enhance.md) |

> *注：每行均为各自 11～26 年同窗口对比（括号内为死拿对应标的：境内标普 `513500`、美股标普、美元黄金 `GLD`、比特币）。\*国内三组合近十年受美股与黄金双牛市顺风，实盘预期建议放低至年化 8%～12%；A 股宽基与红利低波实测不适合择时，直接定投或搭国债/黄金最稳。*

## 接着看什么

- **普通读者必看**：[实盘 4 条避坑铁律](docs/strategies/pitfalls.md)（国内溢价、币圈合约、黄金风险、已证伪清单） · [一次投入 vs 每月定投体验](docs/strategies/holding-experience.md) · [大白话术语表](docs/glossary.md)
- **研究者与复现**：[全仓研究总台账](docs/research-ledger.md) · [策略索引](docs/strategies/research-index.md) · [仓库结构说明](docs/repository-structure.md) · 自动化纸面记账见 [trading](../trading/README.md)

<details>
<summary>点击展开：本地复现、一键查最新信号与研究仪表盘命令</summary>

```sh
uv sync                                             # 安装并锁定 Python 3.12 环境
uv run python check_env.py                          # 检查本地环境与行情接口
uv run pytest                                       # 运行自动化测试与文档链接守卫
uv run python scripts/check_live_sp500_signals.py   # 一键查看三组合、标普/纳指、黄金、BTC 最新趋势与波动状态
uv run jupyter lab                                  # 打开 research/notebooks/
make dashboard-install && make dashboard            # 启动本地研究仪表盘
```

</details>
