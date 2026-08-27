import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RetailerOfferCard } from "@/components/product/RetailerOfferCard";
import { offerFixture } from "@/test/fixtures";

describe("RetailerOfferCard", () => {
  it("renders seller, prices, availability, source URL, and freshness", () => {
    render(
      <RetailerOfferCard
        offer={offerFixture}
        priceHistoryHref="/products/11111111-1111-1111-1111-111111111111/price-history"
      />,
    );

    expect(screen.getByRole("heading", { name: "Fictional Mock Mart A" })).toBeInTheDocument();
    expect(screen.getByText(/Seller: Fictional Mock Mart A/)).toBeInTheDocument();
    expect(screen.getByText("In stock")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View on retailer site" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View price history" })).toBeInTheDocument();
    expect(screen.getByText(/Data freshness: Fresh/)).toBeInTheDocument();
  });
});
