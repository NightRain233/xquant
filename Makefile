# 默认显示帮助信息，直接运行 make 即可查看全部命令
.DEFAULT_GOAL := help

# 仪表盘目录和包管理工具
DASHBOARD_DIR := dashboard
NPM := npm

# 声明伪目标，避免与同名文件或目录冲突
.PHONY: help
.PHONY: dashboard dashboard-dev dashboard-dev-fresh dashboard-preview
.PHONY: dashboard-install dashboard-benchmarks dashboard-refresh dashboard-refresh-all
.PHONY: dashboard-test dashboard-build dashboard-check

# 中文命令帮助
help:
	@echo "xquant 策略报告命令："
	@echo ""
	@echo "启动报告："
	@echo "  make dashboard              启动策略报告（日常使用，本地数据）"
	@echo "  make dashboard-dev          与 make dashboard 相同"
	@echo "  make dashboard-dev-fresh    获取最新基准数据、重建报告数据并启动"
	@echo "  make dashboard-preview      预览生产构建结果"
	@echo ""
	@echo "数据更新："
	@echo "  make dashboard-install      安装仪表盘依赖"
	@echo "  make dashboard-refresh      使用本地输出重建 dashboard/public/data"
	@echo "  make dashboard-refresh-all  获取外部基准数据并重建报告数据"
	@echo "  make dashboard-benchmarks   仅获取外部基准 CSV 数据"
	@echo ""
	@echo "检查与构建："
	@echo "  make dashboard-test         运行一次仪表盘测试"
	@echo "  make dashboard-build        构建生产版本"
	@echo "  make dashboard-check        重建数据、运行测试并构建生产版本"

# 报告启动命令
dashboard: dashboard-dev

dashboard-install:
	cd $(DASHBOARD_DIR) && $(NPM) install

# 数据获取与重建命令
dashboard-benchmarks:
	cd $(DASHBOARD_DIR) && $(NPM) run fetch:benchmarks

dashboard-refresh:
	cd $(DASHBOARD_DIR) && $(NPM) run build:data

dashboard-refresh-all: dashboard-benchmarks dashboard-refresh

dashboard-dev:
	cd $(DASHBOARD_DIR) && $(NPM) run build:data && $(NPM) run dev -- --host 127.0.0.1

dashboard-dev-fresh:
	cd $(DASHBOARD_DIR) && $(NPM) run fetch:benchmarks && $(NPM) run build:data && $(NPM) run dev -- --host 127.0.0.1

# 测试与生产构建命令
dashboard-test:
	cd $(DASHBOARD_DIR) && $(NPM) test -- --run

dashboard-build:
	cd $(DASHBOARD_DIR) && $(NPM) run build

dashboard-check: dashboard-refresh dashboard-test dashboard-build

dashboard-preview:
	cd $(DASHBOARD_DIR) && $(NPM) run preview -- --host 127.0.0.1
