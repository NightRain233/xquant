# Def200 手动试运行的新电脑入口

继续对话请先读同级trading仓库的 `docs/def200-manual-launch-handoff-2026-09-06.md`：

https://github.com/NightRain233/trading/blob/main/docs/def200-manual-launch-handoff-2026-09-06.md

已选 Core80 + LVT20 + Def200 Cash，小额预算暂按8,000元准备。不是Core90 Bull10，也不是全仓LVT。计划2026年9月10日收盘后计算新信号，9月11日条件满足后由用户手动执行；513100高溢价、真实费率、具体next-close委托/未成交规则仍需确认。没有无条件开仓或自动任务授权。

主要证据目录：

- `outputs/def200-cash-manual-review-2026-09-06-v2/`：当前合同历史数量/现金/整手执行核验。
- `outputs/def200-cash-minimum-capital-2026-09-06-v2/`：最新独立快照与固定预算比较；8,000元的66%现金是首次建仓示例，50是防守卖出事件数。
- `outputs/theme-alpha-lvt-recent-3m-2026-09-06/`：最新三个月研究比较，不是独立LVT真实前向成交账本。

两个仓库建议并排克隆；相关脚本默认解析同级trading，也支持 `TRADING_ROOT`。使用各仓库uv依赖，安全配置行情凭证。Parquet快照被Git忽略，研究脚本不能在缺失输入时直接复现；重新拉取数据应使用新目录并记录数据时点。历史报告中的旧绝对路径只作来源记录。

禁止以研究CSV导入真实账户，禁止回填旧纸面账户，禁止为适应小资金偷偷修改20%卫星或买入未入选资产。不再扩展ST/MA参数搜索。
