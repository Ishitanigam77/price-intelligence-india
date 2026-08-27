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
});
