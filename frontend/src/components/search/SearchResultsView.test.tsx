import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SearchResultsView } from "@/components/search/SearchResultsView";
import { searchPageFixture, pricesFixture, searchHitFixture } from "@/test/fixtures";
import { navigationState } from "@/test/navigation";

vi.mock("@/lib/api", () => ({
  searchProducts: vi.fn(),
  getProductPrices: vi.fn(),
}));

import { getProductPrices, searchProducts } from "@/lib/api";

describe("Search results rendering", () => {
  beforeEach(() => {
    navigationState.search = "q=aurora";
    vi.mocked(searchProducts).mockReset();
    vi.mocked(getProductPrices).mockReset();
  });

  it("renders product name, variant, price, retailers, and details link from a success response", async () => {
    vi.mocked(searchProducts).mockResolvedValue(searchPageFixture());
    vi.mocked(getProductPrices).mockResolvedValue(pricesFixture);

    render(<SearchResultsView />);

    expect(
      await screen.findByRole("heading", { name: /Fictional Orchard Aurora/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Exact variant: 128 GB · Midnight/)).toBeInTheDocument();
    expect(screen.getByText("Lowest verified price")).toBeInTheDocument();
    expect(screen.getByText("Available retailers")).toBeInTheDocument();
    expect(screen.getByText("Cheapest retailer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View product details" })).toHaveAttribute(
      "href",
      `/products/${searchHitFixture.product.id}?variant=${searchHitFixture.variant.id}`,
    );
    expect(screen.queryByRole("status", { name: /Loading/i })).not.toBeInTheDocument();
  });

  it("renders an empty state when the API returns no items", async () => {
    vi.mocked(searchProducts).mockResolvedValue(searchPageFixture([]));

    render(<SearchResultsView />);

    expect(
      await screen.findByRole("heading", { name: "No matching products found." }),
    ).toBeInTheDocument();
    expect(screen.getByText(/results are never invented/i)).toBeInTheDocument();
    expect(screen.queryByText(/backend returned no observed listings/i)).not.toBeInTheDocument();
  });

  it("renders an error state when search fails", async () => {
    vi.mocked(searchProducts).mockRejectedValue(new Error("Search upstream failed"));

    render(<SearchResultsView />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Search upstream failed");
  });
});
