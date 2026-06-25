import { useEffect, useState } from "react";
import type { StrategyCatalog, StrategyPaperData, StrategyResearchData, StrategyReportData, StrategySummaryPackage } from "./types";

type LoadState<T> =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: T; error: null }
  | { status: "error"; data: null; error: string };

type StrategyDataState =
  | { status: "idle"; strategy: null; error: null }
  | { status: "loading"; strategy: null; error: null }
  | { status: "ready"; strategy: StrategySummaryPackage; error: null }
  | { status: "error"; strategy: null; error: string };

type StrategyCatalogState =
  | { status: "loading"; catalog: null; error: null }
  | { status: "ready"; catalog: StrategyCatalog; error: null }
  | { status: "error"; catalog: null; error: string };

export function useStrategyCatalog(): StrategyCatalogState {
  const [state, setState] = useState<StrategyCatalogState>({
    status: "loading",
    catalog: null,
    error: null
  });

  useEffect(() => {
    let cancelled = false;

    async function loadCatalog() {
      try {
        const response = await fetch("/data/strategies/index.json");

        if (!response.ok) {
          throw new Error(`Failed to load strategy catalog: ${response.status}`);
        }

        const catalog = (await response.json()) as StrategyCatalog;

        if (!cancelled) {
          setState({ status: "ready", catalog, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "error",
            catalog: null,
            error: error instanceof Error ? error.message : "Unknown catalog loading error"
          });
        }
      }
    }

    void loadCatalog();

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

export function useStrategyData(strategyId: string | null = "btc-supertrend-satellite"): StrategyDataState {
  const [state, setState] = useState<StrategyDataState>({
    status: strategyId === null ? "idle" : "loading",
    strategy: null,
    error: null
  });

  useEffect(() => {
    let cancelled = false;

    async function loadStrategy() {
      if (strategyId === null) {
        setState({ status: "idle", strategy: null, error: null });
        return;
      }

      try {
        setState({ status: "loading", strategy: null, error: null });
        const response = await fetch(`/data/strategies/${strategyId}/strategy.json`);

        if (!response.ok) {
          throw new Error(`Failed to load strategy summary: ${response.status}`);
        }

        const strategy = (await response.json()) as StrategySummaryPackage;

        if (!cancelled) {
          setState({ status: "ready", strategy, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "error",
            strategy: null,
            error: error instanceof Error ? error.message : "Unknown data loading error"
          });
        }
      }
    }

    void loadStrategy();

    return () => {
      cancelled = true;
    };
  }, [strategyId]);

  return state;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to load ${url}: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function useStrategyReportData(strategyId: string): LoadState<StrategyResearchData> {
  const [state, setState] = useState<LoadState<StrategyResearchData>>({
    status: "loading",
    data: null,
    error: null
  });

  useEffect(() => {
    let cancelled = false;

    async function loadReportData() {
      try {
        setState({ status: "loading", data: null, error: null });
        const baseUrl = `/data/strategies/${strategyId}`;
        const [report, navSeries, underwaterSeries, annualReturns, monthlyStats] = await Promise.all([
          fetchJson<StrategyReportData>(`${baseUrl}/report.json`),
          fetchJson<StrategyResearchData["navSeries"]>(`${baseUrl}/nav-series.json`),
          fetchJson<StrategyResearchData["underwaterSeries"]>(`${baseUrl}/underwater-series.json`),
          fetchJson<StrategyResearchData["annualReturns"]>(`${baseUrl}/annual-returns.json`),
          fetchJson<StrategyResearchData["monthlyStats"]>(`${baseUrl}/monthly-stats.json`)
        ]);

        if (!cancelled) {
          setState({
            status: "ready",
            data: {
              ...report,
              navSeries,
              underwaterSeries,
              annualReturns,
              monthlyStats
            },
            error: null
          });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "error",
            data: null,
            error: error instanceof Error ? error.message : "Unknown report data loading error"
          });
        }
      }
    }

    void loadReportData();

    return () => {
      cancelled = true;
    };
  }, [strategyId]);

  return state;
}

export function useStrategyPaperData(strategyId: string): LoadState<StrategyPaperData> {
  const [state, setState] = useState<LoadState<StrategyPaperData>>({
    status: "loading",
    data: null,
    error: null
  });

  useEffect(() => {
    let cancelled = false;

    async function loadPaperData() {
      try {
        setState({ status: "loading", data: null, error: null });
        const data = await fetchJson<StrategyPaperData>(`/data/strategies/${strategyId}/paper.json`);

        if (!cancelled) {
          setState({ status: "ready", data, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "error",
            data: null,
            error: error instanceof Error ? error.message : "Unknown paper data loading error"
          });
        }
      }
    }

    void loadPaperData();

    return () => {
      cancelled = true;
    };
  }, [strategyId]);

  return state;
}
