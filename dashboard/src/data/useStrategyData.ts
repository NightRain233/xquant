import { useEffect, useState } from "react";
import type { StrategyCatalog, StrategyPackage } from "./types";

type StrategyDataState =
  | { status: "idle"; strategy: null; error: null }
  | { status: "loading"; strategy: null; error: null }
  | { status: "ready"; strategy: StrategyPackage; error: null }
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
          throw new Error(`Failed to load strategy data: ${response.status}`);
        }

        const strategy = (await response.json()) as StrategyPackage;

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
