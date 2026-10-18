# dividend-lowvol-csi2000-2026-10-18

红利低波(全收益 H20269) + 中证2000(价格 932000，2023-08 才发布，之前为倒推) 的四套预先固定规则研究。报告：`docs/notes/dividend-lowvol-csi2000-2026-10-18-review.md`。

- `config.json`：事先固定的参数（只跑一次）
- `data_manifest.json`：数据来源、区间、SHA256（原始文件在被 git 忽略的 `cache/`，可用 `scripts/fetch_dividend_lowvol_csi2000_data.py` 重取）
- `summary.csv`：年化、回撤、最长回本、波动、滚动3年最差、换手、成本
- `yearly_returns.csv`、`key_periods.csv`、`key_periods_index_context.csv`、`correlations.csv`
- `subsamples.csv`（2014-08~2019 / 2020~）、`sensitivity.csv`（敏感性，不用于选参数）
- `etf_vs_index.csv`、`dividend_gap.csv`
- `nav_daily.csv`、`trades.csv`、`weights_daily_C.csv`
