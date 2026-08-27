"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ProductGrid } from "@/components/product/ProductGrid";
import { SearchBar } from "@/components/search/SearchBar";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { getProductPrices, searchProducts } from "@/lib/api";
import { useAsync } from "@/lib/hooks/useAsync";
import {
  attachVerifiedPrices,
  groupSearchHits,
  variantPriceMap,
  type GroupedSearchCard,
} from "@/lib/search/groupHits";
import type { ProductSearchPage, VariantPricesRead } from "@/lib/types/api";

const PAGE_SIZE = 50;

interface SearchPayload {
  page: ProductSearchPage;
  cards: GroupedSearchCard[];
}

async function loadSearch(query: string, offset: number): Promise<SearchPayload> {
  const page = await searchProducts({ q: query, limit: PAGE_SIZE, offset });
  const cards = groupSearchHits(page.items);
  const uniqueProductIds = [...new Set(cards.map((card) => card.product.id))];
  const maps = await Promise.all(
    uniqueProductIds.map(async (productId) => {
      try {
        const prices = await getProductPrices(productId);
        return variantPriceMap(productId, prices.variants);
      } catch {
        return new Map<string, VariantPricesRead>();
      }
    }),
  );
  const combined = new Map<string, VariantPricesRead>();
  for (const map of maps) {
    for (const [key, value] of map) {
      combined.set(key, value);
    }
  }
  return { page, cards: attachVerifiedPrices(cards, combined) };
}

export function SearchResultsView() {
  const params = useSearchParams();
  const query = (params.get("q") ?? "").trim();
  const offset = Math.max(0, Number(params.get("offset") ?? "0") || 0);
  const state = useAsync(() => loadSearch(query, offset), [query, offset], {
    enabled: query.length > 0,
  });

  if (!query) {
    return (
      <EmptyState
        title="Enter a search"
        description="Enter a product name to search across supported Indian retailers."
        action={<SearchBar />}
      />
    );
  }

  if (state.status === "loading" || state.status === "idle") {
    return <LoadingSkeleton label="Searching products" rows={4} />;
  }

  if (state.status === "error") {
    return <ErrorState title="Search failed" error={state.error} onRetry={state.reload} />;
  }

  const { page, cards } = state.data;
  const hasMore = page.offset + page.items.length < page.total;
  const prevOffset = Math.max(0, page.offset - page.limit);
  const nextOffset = page.offset + page.limit;

  return (
    <div className="space-y-6">
      <SearchBar initialQuery={query} size="hero" />
      <p className="text-sm text-ink-muted" aria-live="polite">
        {page.total === 0
          ? `No matching products found for “${page.query}”.`
          : `Showing ${page.items.length} result${page.items.length === 1 ? "" : "s"} (total ${page.total}) for “${page.query}”, grouped by exact variant.`}
      </p>
      {page.failures.length > 0 ? (
        <div role="status" className="rounded-xl bg-warn-light px-4 py-3 text-sm text-warn">
          Some stores could not be checked. Matching results from stores that responded are still
          shown.
        </div>
      ) : null}
      {cards.length === 0 ? (
        <EmptyState
          title="No matching products found."
          description="Results are never invented to fill this page."
        />
      ) : (
        <ProductGrid cards={cards} />
      )}
      {page.total > page.limit ? (
        <nav aria-label="Search results pagination" className="flex justify-between gap-3">
          {page.offset > 0 ? (
            <Link
              href={`/search?q=${encodeURIComponent(query)}&offset=${prevOffset}`}
              className="inline-flex min-h-11 items-center rounded-xl border border-ink px-4 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              Previous page
            </Link>
          ) : (
            <span />
          )}
          {hasMore ? (
            <Link
              href={`/search?q=${encodeURIComponent(query)}&offset=${nextOffset}`}
              className="inline-flex min-h-11 items-center rounded-xl bg-ink px-4 text-sm font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              Next page
            </Link>
          ) : null}
        </nav>
      ) : null}
    </div>
  );
}
