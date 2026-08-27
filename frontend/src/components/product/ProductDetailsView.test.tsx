import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProductDetailsView } from "@/components/product/ProductDetailsView";
import { historyFixture, pricesFixture, productFixture, variantFixture } from "@/test/fixtures";

vi.mock("@/lib/api", () => ({
  getProduct: vi.fn(),
  listProductVariants: vi.fn(),
  getProductPrices: vi.fn(),
  getProductHistory: vi.fn(),
}));

import { getProduct, getProductHistory, getProductPrices, listProductVariants } from "@/lib/api";

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
  });

  it("renders product information, variant, lowest verified price, and history summary", async () => {
    render(<ProductDetailsView productId={productFixture.id} />);

    expect(await screen.findByRole("heading", { name: productFixture.name })).toBeInTheDocument();
    expect(screen.getByText(/Fixture product used only in frontend tests/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /128 GB · Midnight/ })).toBeInTheDocument();
    expect(screen.getByText("Lowest verified price")).toBeInTheDocument();
    expect(screen.getByText("Retailer offers")).toBeInTheDocument();
    expect(screen.getByText("Price history snapshot")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open full price history" })).toHaveAttribute(
      "href",
      `/products/${productFixture.id}/price-history?variant=${variantFixture.id}`,
    );
  });

  it("renders retailer offers from the comparison API", async () => {
    render(<ProductDetailsView productId={productFixture.id} />);

    expect(
      await screen.findByRole("heading", { name: "Fictional Mock Mart A" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Seller: Fictional Mock Mart A/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open retailer source URL" })).toHaveAttribute(
      "href",
      "https://mock-retailer-a.example.test/A-MOB-1001",
    );
    expect(screen.getByText("Effective price")).toBeInTheDocument();
    expect(screen.getByText("Displayed price")).toBeInTheDocument();
  });
});
