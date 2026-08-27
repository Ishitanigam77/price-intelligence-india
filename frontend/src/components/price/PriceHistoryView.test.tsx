import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PriceHistoryView } from "@/components/price/PriceHistoryView";
import { historyFixture, insufficientHistoryFixture, productFixture } from "@/test/fixtures";

vi.mock("@/lib/api", () => ({
  getProduct: vi.fn(),
  getProductHistory: vi.fn(),
}));

import { getProduct, getProductHistory } from "@/lib/api";

describe("Historical price data rendering", () => {
  beforeEach(() => {
    vi.mocked(getProduct).mockResolvedValue(productFixture);
  });

  it("renders observations, calculated aggregates, and a chart when history exists", async () => {
    vi.mocked(getProductHistory).mockResolvedValue(historyFixture);

    render(<PriceHistoryView productId={productFixture.id} />);

    expect(await screen.findByRole("heading", { name: productFixture.name })).toBeInTheDocument();
    expect(screen.getByText("7-day average")).toBeInTheDocument();
    expect(screen.getByText("30-day average")).toBeInTheDocument();
    expect(screen.getByText("90-day average")).toBeInTheDocument();
    expect(screen.getByText("180-day average")).toBeInTheDocument();
    expect(screen.getByText("Historical low")).toBeInTheDocument();
    expect(screen.getByText("Historical high")).toBeInTheDocument();
    expect(screen.getByText("Current percentile")).toBeInTheDocument();
    expect(screen.getByText("Volatility")).toBeInTheDocument();
    expect(screen.getByText("Percentage change")).toBeInTheDocument();
    expect(screen.getByText("Trend")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Historical observed prices/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Displayed" })).toBeInTheDocument();
    expect(screen.getByText("Predicted · not available")).toBeInTheDocument();
  });

  it("renders the insufficient-history state without fabricating values", async () => {
    vi.mocked(getProductHistory).mockResolvedValue(insufficientHistoryFixture);

    render(<PriceHistoryView productId={productFixture.id} />);

    expect(
      await screen.findByRole("heading", { name: "Insufficient history for a chart" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Insufficient history").length).toBeGreaterThan(0);
    expect(
      screen.queryByRole("img", { name: /Historical observed prices/ }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText(/No qualifying observations/).length).toBeGreaterThan(0);
  });
});
