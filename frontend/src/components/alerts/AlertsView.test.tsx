import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertsView } from "@/components/alerts/AlertsView";
import { productFixture } from "@/test/fixtures";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: true,
    getToken: async () => "test-session-token",
  }),
}));

vi.mock("@/lib/api/alerts", () => ({
  listAlerts: vi.fn(),
  updateAlert: vi.fn(),
}));

import { listAlerts } from "@/lib/api/alerts";

describe("AlertsView", () => {
  it("renders the authenticated user's alerts", async () => {
    vi.mocked(listAlerts).mockResolvedValue({
      items: [
        {
          id: "al-1",
          product_id: productFixture.id,
          threshold_amount: "499.00",
          currency: "INR",
          is_enabled: true,
          product: productFixture,
          created_at: productFixture.created_at,
          updated_at: productFixture.updated_at,
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });

    render(<AlertsView />);

    expect(await screen.findByRole("heading", { name: "Price alerts" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: productFixture.name })).toBeInTheDocument();
    expect(listAlerts).toHaveBeenCalledWith({ accessToken: "test-session-token" });
  });
});
