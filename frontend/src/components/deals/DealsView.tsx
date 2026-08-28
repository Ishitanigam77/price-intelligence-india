"use client";

import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { listDeals } from "@/lib/api";
import { useAsync } from "@/lib/hooks/useAsync";

export function DealsView() {
  const state = useAsync(() => listDeals({ limit: 50, offset: 0 }), []);

  if (state.status === "loading" || state.status === "idle") {
    return <LoadingSkeleton label="Loading deals" />;
  }
  if (state.status === "error") {
    return (
      <ErrorState title="Deals could not be loaded" error={state.error} onRetry={state.reload} />
    );
  }

  const { items, total } = state.data;

  if (total === 0 || items.length === 0) {
    return (
      <EmptyState title="No verified deals yet." description="Discounts are never invented." />
    );
  }

  return (
    <ul className="grid gap-4">
      {items.map((item, index) => (
        <li key={index} className="rounded-2xl bg-paper-card p-4 shadow-card">
          Verified deal {index + 1}
        </li>
      ))}
    </ul>
  );
}
