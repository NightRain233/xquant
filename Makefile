.DEFAULT_GOAL := help

DASHBOARD_DIR := dashboard
NPM := npm

.PHONY: help dashboard dashboard-dev dashboard-dev-fresh dashboard-refresh dashboard-refresh-all dashboard-benchmarks dashboard-test dashboard-build dashboard-check dashboard-preview dashboard-install

help:
	@echo "xquant dashboard commands:"
	@echo "  make dashboard              Start dashboard dev server with local static data"
	@echo "  make dashboard-dev          Same as make dashboard"
	@echo "  make dashboard-dev-fresh    Fetch benchmark data, rebuild dashboard data, then start dev server"
	@echo "  make dashboard-refresh      Rebuild dashboard/public/data from existing local outputs"
	@echo "  make dashboard-refresh-all  Fetch external benchmarks, then rebuild dashboard data"
	@echo "  make dashboard-benchmarks   Fetch external benchmark CSVs only"
	@echo "  make dashboard-test         Run dashboard tests once"
	@echo "  make dashboard-build        Build dashboard for production"
	@echo "  make dashboard-check        Rebuild data, run tests, and build"
	@echo "  make dashboard-preview      Preview production build"

dashboard: dashboard-dev

dashboard-install:
	cd $(DASHBOARD_DIR) && $(NPM) install

dashboard-benchmarks:
	cd $(DASHBOARD_DIR) && $(NPM) run fetch:benchmarks

dashboard-refresh:
	cd $(DASHBOARD_DIR) && $(NPM) run build:data

dashboard-refresh-all: dashboard-benchmarks dashboard-refresh

dashboard-dev:
	cd $(DASHBOARD_DIR) && $(NPM) run build:data && $(NPM) run dev -- --host 127.0.0.1

dashboard-dev-fresh:
	cd $(DASHBOARD_DIR) && $(NPM) run fetch:benchmarks && $(NPM) run build:data && $(NPM) run dev -- --host 127.0.0.1

dashboard-test:
	cd $(DASHBOARD_DIR) && $(NPM) test -- --run

dashboard-build:
	cd $(DASHBOARD_DIR) && $(NPM) run build

dashboard-check: dashboard-refresh dashboard-test dashboard-build

dashboard-preview:
	cd $(DASHBOARD_DIR) && $(NPM) run preview -- --host 127.0.0.1
