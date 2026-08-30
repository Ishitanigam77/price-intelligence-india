"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useState } from "react";

import { SignInRequired } from "@/components/auth/SignInRequired";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { listAlerts, updateAlert } from "@/lib/api/alerts";
import { formatMoney } from "@/lib/format/money";
import { useAsync } from "@/lib/hooks/useAsync";
import type { AlertRead } from "@/lib/types/api";

export function AlertsView() {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const [reloadToken, setReloadToken] = useState(0);

  const state = useAsync(
    async (): Promise<AlertRead[]> => {
      const accessToken = await getToken();
      const page = await listAlerts({ accessToken });
      return page.items;
    },
    [getToken, reloadToken],
    { enabled: isLoaded && Boolean(isSignedIn) },
  );

  async function toggle(item: AlertRead) {
    const accessToken = await getToken();
    await updateAlert(item.id, { is_enabled: !item.is_enabled }, { accessToken });
    setReloadToken((value) => value + 1);
  }

  if (isLoaded && !isSignedIn) {
    return <SignInRequired resource="alerts" />;
  }
  if (!isLoaded || state.status === "idle" || state.status === "loading") {
    return <LoadingSkeleton label="Loading your alerts" rows={4} />;
  }
  if (state.status === "error") {
    return (
      <ErrorState title="Alerts could not be loaded" error={state.error} onRetry={state.reload} />
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-4xl text-ink">Price alerts</h1>
        <p className="text-ink-muted">
          Alert rules belong to your account. Notification delivery is not part of this release.
        </p>
      </header>
      {state.data.length === 0 ? (
        <EmptyState
          title="You have no alerts"
          description="Open a product and set a threshold to create an alert for your account only."
          action={
            <Link
              href="/"
              className="inline-flex min-h-11 items-center rounded-xl bg-brand px-4 text-sm font-semibold text-white hover:bg-brand-dark"
            >
              Search products
            </Link>
          }
        />
      ) : (
        <ul className="space-y-3">
          {state.data.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-paper-muted bg-paper-card p-4 shadow-card"
            >
              <div>
                <Link
                  href={`/products/${item.product_id}`}
                  className="font-display text-xl text-ink hover:text-brand"
                >
                  {item.product?.name ?? "Product"}
                </Link>
                <p className="text-sm text-ink-muted">
                  Threshold{" "}
                  {formatMoney(item.threshold_amount, item.currency) ?? item.threshold_amount} ·{" "}
                  {item.is_enabled ? "Enabled" : "Paused"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void toggle(item)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-brand hover:bg-brand-light"
              >
                {item.is_enabled ? "Pause" : "Enable"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
