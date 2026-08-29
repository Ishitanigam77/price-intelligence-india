import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SignInView } from "@/components/auth/SignInView";

describe("SignInView", () => {
  it("does not fabricate a signed-in session when Clerk is unconfigured", () => {
    render(<SignInView />);
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByText(/Clerk is not configured/i)).toBeInTheDocument();
    expect(screen.queryByText(/welcome back/i)).not.toBeInTheDocument();
  });
});
