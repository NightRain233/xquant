import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TargetWeightsPanel } from "./TargetWeightsPanel";

describe("TargetWeightsPanel", () => {
  it("shows LVT internal weights and whole-portfolio contributions", () => {
    render(
      <TargetWeightsPanel
        rows={[
          {
            candidate: "Def200_Cash / BIMONTHLY",
            weights: {
              纳指100ETF: 0.25,
              芯片ETF: 0.055,
              通信ETF: 0.058
            }
          }
        ]}
        sleeves={[
          {
            candidate: "Def200_Cash / BIMONTHLY",
            sleeve: "LVT20",
            allocation: 0.2,
            weights: {
              纳指100ETF: 0.4334,
              芯片ETF: 0.2774,
              通信ETF: 0.2892
            }
          }
        ]}
      />
    );

    expect(screen.getByRole("heading", { name: "LVT20 袖层拆解" })).toBeInTheDocument();
    expect(screen.getByText(/同一资产可能同时属于 Core 和 LVT/)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "43.34%" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "8.67%" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "27.74%" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "5.55%" })).toBeInTheDocument();
  });
});
