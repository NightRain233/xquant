import { useEffect, useState } from "react";
import type { StrategyPackage } from "./types";

type StrategyDataState =
  | { status: "loading"; strategy: null; error: null }
  | { status: "ready"; strategy: StrategyPackage; error: null }
  | { status: "error"; strategy: null; error: string };

export function useStrategyData(strategyId = "btc-supertrend-satellite"): StrategyDataState {
  const [state, setState] = useState<StrategyDataState>({
    status: "loading",
    strategy: null,
    error: null
  });

  useEffect(() => {
    let cancelled = false;

    async function loadStrategy() {
      try {
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
