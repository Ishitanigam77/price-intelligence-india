import { Suspense } from "react";
import type { Metadata } from "next";

import { SearchResultsView } from "@/components/search/SearchResultsView";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";

export const metadata: Metadata = {
  title: "Search results",
};

export default function SearchPage() {
  return (
    <div>
      <h1 className="mb-6 font-display text-3xl text-ink">Search results</h1>
      <Suspense fallback={<LoadingSkeleton label="Loading search" />}>
        <SearchResultsView />
      </Suspense>
    </div>
  );
}
