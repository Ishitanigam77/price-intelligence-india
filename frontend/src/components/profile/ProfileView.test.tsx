import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfileView } from "@/components/profile/ProfileView";

const authState = {
  isLoaded: true,
  isSignedIn: true,
  getToken: async () => "test-session-token",
};

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => authState,
  useUser: () => ({
    user: { fullName: "Ada Lovelace", primaryEmailAddress: { emailAddress: "ada@example.test" } },
  }),
}));

vi.mock("@/lib/api/profile", () => ({
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

import { getProfile } from "@/lib/api/profile";

describe("ProfileView", () => {
  it("renders the authenticated user's profile and not another user's identity", async () => {
    vi.mocked(getProfile).mockResolvedValue({
      id: "11111111-1111-1111-1111-111111111111",
      clerk_user_id: "user_ada",
      email: "ada@example.test",
      display_name: "Ada",
      preferences: { email_alerts_enabled: true, default_currency: "INR" },
      created_at: "2026-08-29T12:00:00+00:00",
      updated_at: "2026-08-29T12:00:00+00:00",
    });

    render(<ProfileView />);

    expect(await screen.findByRole("heading", { name: "Your profile" })).toBeInTheDocument();
    expect(screen.getByText("user_ada")).toBeInTheDocument();
    expect(screen.getByText("ada@example.test")).toBeInTheDocument();
    expect(getProfile).toHaveBeenCalledWith({ accessToken: "test-session-token" });
  });

  it("asks the user to sign in instead of rendering another user's profile", () => {
    vi.mocked(getProfile).mockClear();
    authState.isSignedIn = false;
    render(<ProfileView />);
    expect(screen.getByRole("heading", { name: "Sign in required" })).toBeInTheDocument();
    expect(getProfile).not.toHaveBeenCalled();
    authState.isSignedIn = true;
  });
});
