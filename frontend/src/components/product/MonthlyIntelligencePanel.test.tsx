import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MonthlyIntelligencePanel } from "@/components/product/MonthlyIntelligencePanel";
import { monthlyFixture } from "@/test/fixtures";

describe("Monthly intelligence panel", () => {
  it("renders available monthly statistics even when best buying month is missing", () => {
    render(
      <MonthlyIntelligencePanel
        monthly={{
          ...monthlyFixture,
          best_buying_month: null,
          best_buying_month_price: {
            ...monthlyFixture.best_buying_month_price,
            status: "insufficient_history",
            value: null,
          },
        }}
      />,
    );

    expect(screen.getByText("INSUFFICIENT HISTORY")).toBeInTheDocument();
    expect(screen.getByText("January")).toBeInTheDocument();
    expect(screen.getByText("February")).toBeInTheDocument();
    expect(screen.getAllByText("Median").length).toBeGreaterThan(0);
  });
});
