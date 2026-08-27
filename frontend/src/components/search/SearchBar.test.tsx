import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { SearchBar } from "@/components/search/SearchBar";
import { navigationState } from "@/test/navigation";

describe("Home search interaction", () => {
  beforeEach(() => {
    navigationState.push.mockReset();
    navigationState.pathname = "/";
    navigationState.search = "";
  });

  it("submits the search query to the search results page", async () => {
    const user = userEvent.setup();
    render(<SearchBar />);

    const input = screen.getByRole("searchbox", {
      name: "Search products across Indian retailers",
    });
    await user.type(input, "aurora");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(navigationState.push).toHaveBeenCalledWith("/search?q=aurora");
  });

  it("shows a validation error instead of navigating when the query is blank", async () => {
    const user = userEvent.setup();
    render(<SearchBar />);
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a product name to search.");
    expect(navigationState.push).not.toHaveBeenCalled();
  });
});
