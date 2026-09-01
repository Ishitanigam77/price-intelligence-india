import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SaleTimingPanel } from "@/components/product/SaleTimingPanel";
import {
  insufficientPredictionFixture,
  insufficientSaleIntelligenceFixture,
  recommendationFixture,
  saleIntelligenceFixture,
  salePricePredictionFixture,
  variantFixture,
} from "@/test/fixtures";

describe("Sale timing panel", () => {
  it("renders expected/inferred labels and does not present estimates as guaranteed", () => {
    render(
      <SaleTimingPanel
        intelligence={saleIntelligenceFixture}
        recommendation={recommendationFixture}
        prediction={salePricePredictionFixture}
        variantId={variantFixture.id}
        urgency="patient"
        onUrgencyChange={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Upcoming sale").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Fixture Major Sale").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/MAJOR/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Expected/).length).toBeGreaterThan(0);
    expect(screen.getByText("Predicted sale price")).toBeInTheDocument();
    expect(screen.getByText("Expected best retailer during future sale")).toBeInTheDocument();
    expect(screen.getAllByText("Fictional Mock Mart A").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/not guaranteed retailer announcements/i).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/This is an estimate, not a guaranteed retailer price/)).toBeInTheDocument();
    expect(screen.getByText("Primary recommendation (Phase 11)")).toBeInTheDocument();
    expect(screen.getByText("WAIT")).toBeInTheDocument();
  });

  it("renders insufficient-data states without inventing prices", () => {
    render(
      <SaleTimingPanel
        intelligence={insufficientSaleIntelligenceFixture}
        recommendation={null}
        prediction={insufficientPredictionFixture}
        variantId={variantFixture.id}
        urgency=""
        onUrgencyChange={vi.fn()}
      />,
    );

    expect(screen.getByText("No upcoming sale window")).toBeInTheDocument();
    expect(screen.getByText("PREDICTED — NOT AVAILABLE")).toBeInTheDocument();
    expect(screen.getByText("EXPECTED BEST RETAILER — UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText("Recommendation is not available")).toBeInTheDocument();
  });
});
