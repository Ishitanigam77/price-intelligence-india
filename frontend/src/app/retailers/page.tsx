import type { Metadata } from "next";

import { RetailersView } from "@/components/retailers/RetailersView";

export const metadata: Metadata = {
  title: "Retailers",
};

export default function RetailersPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-4xl text-ink">Retailers</h1>
        <p className="max-w-2xl text-ink-muted">
          This list comes from the backend retailer registry. It is not a claim of live integrations
          with consumer marketplaces.
        </p>
      </header>
      <RetailersView />
    </div>
  );
}
