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
    expect(screen.getByText("Official retailer listing")).toBeInTheDocument();
    expect(screen.getByText("Verified price")).toBeInTheDocument();
    expect(screen.queryByText(/official api/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/displayed only/i)).not.toBeInTheDocument();
  });

  it("describes listed discounts in shopper language", () => {
    render(
      <RetailerOfferCard
        offer={{
          ...offerFixture,
          price_kind: "displayed_only",
          adjustments: [
            {
              kind: "displayed_discount",
              amount: "10000.00",
              source: "listing",
              eligibility: "verified_eligible",
              observed_at: "2026-08-27T16:00:00Z",
              confidence: "high",
              affects_effective_price: true,
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Listed price")).toBeInTheDocument();
    expect(screen.getByText(/Listed discount/)).toBeInTheDocument();
    expect(screen.getByText(/included in the price you would pay/)).toBeInTheDocument();
    expect(screen.queryByText(/displayed discount/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/verified eligible/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/affects effective price/i)).not.toBeInTheDocument();
  });
});
