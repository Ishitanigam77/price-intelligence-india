import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DealsView } from "@/components/deals/DealsView";

vi.mock("@/lib/api", () => ({
  listDeals: vi.fn(),
}));

import { listDeals } from "@/lib/api";

describe("Deals page", () => {
  beforeEach(() => {
    vi.mocked(listDeals).mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  });

  it("shows a coming-soon empty state instead of fabricated deals", async () => {
    render(<DealsView />);
    expect(
      await screen.findByRole("heading", { name: /Coming soon \/ No verified deals available/ }),
    ).toBeInTheDocument();
  });
});
