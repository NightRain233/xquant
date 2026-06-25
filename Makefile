.PHONY: dashboard dashboard-dev dashboard-refresh dashboard-test dashboard-build dashboard-install

dashboard: dashboard-dev

dashboard-install:
	cd dashboard && npm install

dashboard-refresh:
	cd dashboard && npm run refresh:data

dashboard-dev:
	cd dashboard && npm run refresh:data && npm run dev -- --host 127.0.0.1

dashboard-test:
	cd dashboard && npm test -- --run

dashboard-build:
	cd dashboard && npm run build
