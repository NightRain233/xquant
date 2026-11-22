# btc-ashare-buffered-mtf3-2026-11-23

BTC 与 A 股（红利低波及主流宽基全谱）日频防抖三档策略泛化与第一性原理验证输出目录。

## 核心结论速览
- **市场物理指纹** (`market_physics_fingerprint.csv`)：站上 150 日均线后未来 3 个月相对收益差，BTC 为 `+16.84%`、ETH 为 `+8.82%`、QQQ 为 `+2.72%`、SPY 为 `+1.69%`；而 **A 股全部 6 个标的均为负值**（红利低波最极端，达 `-2.75%～-4.12%`，属于典型高股息均值回归橡胶带）。
- **BTC 通过且零调参泛化至 ETH** (`summary_btc_2015.csv`, `summary_eth_2018.csv`, `btc_sensitivity_grid.csv`)：
  - **轨道 1（稳健首选）：日线 SuperTrend(10,3) + 防抖长均线（120d/150d/200d ±5%）三档**（`100%/50%/0%`）— 3×3 参数邻域全部在 BTC 与 ETH 上通过循环位移检验（`p<=0.05`），2021–2026 成熟期明显反超纯日线 SuperTrend 且大幅压低回撤。
  - **轨道 2（极简低换手）：纯双均线防抖三档（`100d/200d ±5%～8%` 或 `50d/120d ±5%`）** — 年换手仅 4～8 次，无需 SuperTrend 指标。
- **A 股（含红利低波）全部未通过趋势择时** (`summary_ashare_timing.csv`)：所有日频缓冲带 MTF-3 变体在红利低波（`H20269` / `510880` / `512890`）上大幅跑输持有且回撤未减反增（`p_sharpe = 0.75~1.00`）；防抖控波动三档（`VOL3`）依赖 2015 单次股灾，在 2016+ 与实盘 `512890`（2020–2026）上未通过检验。
- **A 股红利低波正确解法** (`summary_ashare_structural.csv`, `ashare_rolling_dca.csv`)：靠**选对指数本身 + 傻瓜定投 + 低换手资产分散（搭国债 `511010` / 黄金 `518880`，或坚持主线方案 A 逆波动三组合）**，即便在 2023–2026 黄金大牛市之前（2014–2022）也稳健改善风险收益比。

## 文件清单
- `config.json` / `self_checks.json`：冻结配置、SHA256 校验、现金守恒与零前视扰动自检（`all_passed=true`）
- `market_physics_fingerprint.csv`：10 大资产跨市场趋势延续性指纹
- `summary_btc_2015.csv` / `summary_eth_2018.csv`：BTC 主测（含 10/30/50bp、美债利率、同仓位对照、循环位移检验）与 ETH 零调参外推
- `btc_rolling_dca_5y.csv` / `btc_rolling_starts_annual.csv` / `btc_key_periods.csv` / `btc_annual_returns.csv` / `btc_sensitivity_grid.csv`
- `summary_ashare_timing.csv` / `summary_ashare_structural.csv` / `ashare_rolling_dca.csv`

复现命令：`.venv/bin/python -I scripts/research_btc_ashare_buffered_mtf3_2026_11_23.py`
