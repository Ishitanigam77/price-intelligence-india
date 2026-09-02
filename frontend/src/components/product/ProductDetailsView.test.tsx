import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProductDetailsView } from "@/components/product/ProductDetailsView";
import {
  historyFixture,
  monthlyFixture,
  offerFixture,
  pricesFixture,
  productFixture,
  recommendationFixture,
  saleIntelligenceFixture,
  salePricePredictionFixture,
  variantFixture,
} from "@/test/fixtures";

vi.mock("@/lib/api", () => ({
  getProduct: vi.fn(),
  listProductVariants: vi.fn(),
  getProductPrices: vi.fn(),
  getProductHistory: vi.fn(),
  getProductSaleIntelligence: vi.fn(),
  getProductRecommendation: vi.fn(),
  getProductSalePricePrediction: vi.fn(),
}));

import {
  getProduct,
  getProductHistory,
  getProductPrices,
  getProductRecommendation,
  getProductSaleIntelligence,
  getProductSalePricePrediction,
  listProductVariants,
} from "@/lib/api";

describe("Product details rendering", () => {
  beforeEach(() => {
    vi.mocked(getProduct).mockResolvedValue(productFixture);
    vi.mocked(listProductVariants).mockResolvedValue({
      items: [variantFixture],
      total: 1,
      limit: 200,
      offset: 0,
    });
    vi.mocked(getProductPrices).mockResolvedValue(pricesFixture);
    vi.mocked(getProductHistory).mockResolvedValue(historyFixture);
    vi.mocked(getProductSaleIntelligence).mockResolvedValue(saleIntelligenceFixture);
    vi.mocked(getProductRecommendation).mockResolvedValue(recommendationFixture);
    vi.mocked(getProductSalePricePrediction).mockResolvedValue(salePricePredictionFixture);
  });

  it("renders product information, variant, lowest verified price, and history summary", async () => {
    render(<ProductDetailsView productId={productFixture.id} />);

    expect(await screen.findByRole("heading", { name: productFixture.name })).toBeInTheDocument();
    expect(screen.getByText(/Fixture product used only in frontend tests/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /128 GB · Midnight/ })).toBeInTheDocument();
    expect(screen.getByText("Lowest verified price")).toBeInTheDocument();
    expect(screen.getByText("Current best price")).toBeInTheDocument();
    expect(screen.getByText("All retailer offers")).toBeInTheDocument();
    expect(screen.getByText("Current price intelligence")).toBeInTheDocument();
    expect(screen.getByText("7-day average")).toBeInTheDocument();
    expect(screen.getAllByText("30-day average").length).toBeGreaterThan(0);
    expect(screen.getAllByText("90-day average").length).toBeGreaterThan(0);
    expect(screen.getByText("180-day average")).toBeInTheDocument();
    expect(screen.getAllByText("Historical low").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Historical high").length).toBeGreaterThan(0);
    expect(screen.getByText("Trend")).toBeInTheDocument();
    expect(screen.getAllByText("₹61,000.00").length).toBeGreaterThan(0);
    expect(screen.getAllByText("₹62,000.00").length).toBeGreaterThan(0);
    expect(
      screen.getByText("This is the lowest verified price among current offers."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/ranking fell back/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open full price history" })).toHaveAttribute(
      "href",
      `/products/${productFixture.id}/price-history?variant=${variantFixture.id}`,
    );
  });

  it("renders retailer offers with seller, prices, and retailer site link", async () => {
    render(<ProductDetailsView productId={productFixture.id} />);

    expect(
      await screen.findByRole("heading", { name: "Fictional Mock Mart A" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Seller: Fictional Mock Mart A/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View on retailer site" })).toHaveAttribute(
      "href",
      "https://mock-retailer-a.example.test/A-MOB-1001",
    );
    expect(screen.getByText("Effective price")).toBeInTheDocument();
    expect(screen.getByText("Displayed price")).toBeInTheDocument();
  });

  it("shows a loading skeleton while sale timing intelligence loads", async () => {
    vi.mocked(getProductSaleIntelligence).mockImplementation(
      () => new Promise(() => undefined),
    );
    render(<ProductDetailsView productId={productFixture.id} />);

    expect(await screen.findByText("Monthly price intelligence")).toBeInTheDocument();
    expect(screen.getByText(/Loading sale timing intelligence/)).toBeInTheDocument();
    expect(screen.queryByText("Upcoming sale")).not.toBeInTheDocument();
  });

  it("renders monthly intelligence and sale-timing sections", async () => {
    render(<ProductDetailsView productId={productFixture.id} />);

    expect(await screen.findByText("Monthly price intelligence")).toBeInTheDocument();
    expect(screen.getByText(/Best buying month/i)).toBeInTheDocument();
    expect(screen.getAllByText(/January/).length).toBeGreaterThan(0);
    expect(await screen.findAllByText("Upcoming sale")).not.toHaveLength(0);
    expect(screen.getByText("Predicted sale price")).toBeInTheDocument();
    expect(screen.getByText("Expected best retailer during future sale")).toBeInTheDocument();
    expect(screen.getByText("Ordinary vs major")).toBeInTheDocument();
    expect(screen.getByText("Buying recommendation")).toBeInTheDocument();
    expect(screen.getByText("WAIT")).toBeInTheDocument();
    expect(screen.getByText(/Buying window: WAIT_FOR_MAJOR_SALE/)).toBeInTheDocument();
    expect(screen.getAllByText(/Expected/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/evidence-based estimates and are not guaranteed retailer announcements/i)
        .length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "I need it soon" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "I can wait" })).toBeInTheDocument();
  });

  it("renders every returned retailer offer without truncating to three", async () => {
    const extraOffers = [0, 1, 2, 3].map((index) => ({
      ...offerFixture,
      offer_id: `77777777-7777-7777-7777-77777777777${index}`,
      retailer_id: `33333333-3333-3333-3333-33333333333${index}`,
      retailer_slug: `demo-retailer-${index}`,
      retailer_name: `Demo Retailer ${index + 1}`,
      rank: index + 1,
    }));
    vi.mocked(getProductPrices).mockResolvedValue({
      ...pricesFixture,
      variants: [
        {
          ...pricesFixture.variants[0],
          offers: extraOffers,
          lowest_verified_offer: extraOffers[0],
          offer_count: 4,
          distinct_retailer_count: 4,
          displayed_price_min: extraOffers[0].displayed_price,
          displayed_price_max: extraOffers[3].displayed_price,
        },
      ],
      lowest_verified_offer: extraOffers[0],
    });

    render(<ProductDetailsView productId={productFixture.id} />);

    expect(await screen.findByText("Demo Retailer 1")).toBeInTheDocument();
    expect(screen.getByText("Demo Retailer 2")).toBeInTheDocument();
    expect(screen.getByText("Demo Retailer 3")).toBeInTheDocument();
    expect(screen.getByText("Demo Retailer 4")).toBeInTheDocument();
    expect(screen.getByText(/4 distinct retailers · 4 offers/)).toBeInTheDocument();
  });

  it("still shows monthly statistics when best buying month is unavailable", async () => {
    vi.mocked(getProductHistory).mockResolvedValue({
      ...historyFixture,
      variants: [
        {
          ...historyFixture.variants[0],
          monthly: {
            ...monthlyFixture,
            best_buying_month: null,
            best_buying_month_price: {
              ...monthlyFixture.best_buying_month_price,
              status: "insufficient_history",
              value: null,
            },
          },
        },
      ],
    });

    render(<ProductDetailsView productId={productFixture.id} />);

    expect(await screen.findByText("Monthly price intelligence")).toBeInTheDocument();
    expect(screen.getByText("INSUFFICIENT HISTORY")).toBeInTheDocument();
    expect(screen.getAllByText("January").length).toBeGreaterThan(0);
    expect(screen.getAllByText("February").length).toBeGreaterThan(0);
  });
});
