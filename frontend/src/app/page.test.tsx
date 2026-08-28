import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "@/app/page";

describe("Home page", () => {
  it("renders the prominent search prompt", () => {
    render(<HomePage />);
    expect(
      screen.getByRole("searchbox", { name: "Search products across Indian retailers" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("uses consumer-facing feature copy without API endpoints", () => {
    render(<HomePage />);
    expect(
      screen.getByRole("heading", { name: "Search products across Indian retailers" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Compare verified prices" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "View price history" })).toBeInTheDocument();
    expect(screen.queryByText(/\/api\/v1\//)).not.toBeInTheDocument();
    expect(screen.queryByText(/observed listings/i)).not.toBeInTheDocument();
  });
});
