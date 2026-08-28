"use client";

import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { listRetailers } from "@/lib/api";
import { useAsync } from "@/lib/hooks/useAsync";

export function RetailersView() {
  const state = useAsync(() => listRetailers({ limit: 50, offset: 0 }), []);

  if (state.status === "loading" || state.status === "idle") {
    return <LoadingSkeleton label="Loading retailers" />;
  }
  if (state.status === "error") {
    return (
      <ErrorState
        title="Retailers could not be loaded"
        error={state.error}
        onRetry={state.reload}
      />
    );
  }

  const { items, total } = state.data;
  if (total === 0 || items.length === 0) {
    return (
      <EmptyState
        title="No retailers to show yet."
        description="Retailer names are not invented for this page."
      />
    );
  }

  return (
    <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {items.map((retailer) => (
        <li
          key={retailer.id}
          className="rounded-2xl border border-paper-muted bg-paper-card p-5 shadow-card"
        >
          <h2 className="font-display text-2xl text-ink">{retailer.name}</h2>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-muted">Country</dt>
              <dd className="mt-1 font-medium">{retailer.country_code}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-muted">Status</dt>
              <dd className="mt-1 font-medium">{retailer.is_active ? "Active" : "Inactive"}</dd>
            </div>
          </dl>
          {retailer.website_url ? (
            <a
              href={retailer.website_url}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-4 inline-flex min-h-11 items-center text-sm font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              Open retailer website
            </a>
          ) : (
            <p className="mt-4 text-sm text-ink-muted">
              No website is available for this retailer.
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
