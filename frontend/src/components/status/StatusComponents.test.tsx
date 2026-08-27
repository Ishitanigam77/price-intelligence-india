import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AvailabilityBadge } from "@/components/status/AvailabilityBadge";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";

describe("Accessibility-critical status components", () => {
  it("exposes loading state to assistive technology", () => {
    render(<LoadingSkeleton label="Loading products" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Loading products…")).toBeInTheDocument();
  });

  it("exposes errors as alerts with a retry control", () => {
    render(<ErrorState error={new Error("Network down")} onRetry={() => undefined} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Network down");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("renders empty copy without treating it as an error alert", () => {
    render(<EmptyState title="Nothing here" description="The API returned no rows." />);
    expect(screen.getByRole("heading", { name: "Nothing here" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("labels availability in human-readable text", () => {
    render(<AvailabilityBadge status="out_of_stock" />);
    expect(screen.getByText("Out of stock")).toBeInTheDocument();
  });
});
