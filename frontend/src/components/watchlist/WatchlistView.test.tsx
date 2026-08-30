import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WatchlistView } from "@/components/watchlist/WatchlistView";
import { productFixture } from "@/test/fixtures";

const getToken = vi.fn(async () => "test-session-token");
const authState = { isLoaded: true, isSignedIn: true, getToken };

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => authState,
}));

vi.mock("@/lib/api/watchlists", () => ({
  listWatchlists: vi.fn(),
  deleteWatchlist: vi.fn(),
}));

import { listWatchlists } from "@/lib/api/watchlists";

describe("WatchlistView", () => {
  it("renders only the authenticated user's watchlist items", async () => {
    vi.mocked(listWatchlists).mockResolvedValue({
      items: [
        {
          id: "wl-1",
          product_id: productFixture.id,
          product: productFixture,
          created_at: productFixture.created_at,
          updated_at: productFixture.updated_at,
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
    });

    render(<WatchlistView />);

    expect(await screen.findByRole("heading", { name: "Your watchlist" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: productFixture.name })).toHaveAttribute(
      "href",
      `/products/${productFixture.id}`,
    );
    expect(listWatchlists).toHaveBeenCalledWith({ accessToken: "test-session-token" });
  });

  it("asks the user to sign in instead of loading another account's data", () => {
    vi.mocked(listWatchlists).mockClear();
    authState.isSignedIn = false;
    render(<WatchlistView />);
    expect(screen.getByRole("heading", { name: "Sign in required" })).toBeInTheDocument();
    expect(listWatchlists).not.toHaveBeenCalled();
    authState.isSignedIn = true;
  });
});
