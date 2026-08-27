import type { Metadata } from "next";

import { DealsView } from "@/components/deals/DealsView";

export const metadata: Metadata = {
  title: "Deals",
};

export default function DealsPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-4xl text-ink">Deals</h1>
        <p className="max-w-2xl text-ink-muted">
          Only deals produced by the backend are shown. This page never fabricates discounts or
          retailer promotions.
        </p>
      </header>
      <DealsView />
    </div>
  );
}
