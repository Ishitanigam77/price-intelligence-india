"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useState } from "react";

import { SignInRequired } from "@/components/auth/SignInRequired";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { deleteWatchlist, listWatchlists } from "@/lib/api/watchlists";
import { useAsync } from "@/lib/hooks/useAsync";
import type { WatchlistRead } from "@/lib/types/api";

export function WatchlistView() {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const [reloadToken, setReloadToken] = useState(0);

  const state = useAsync(
    async (): Promise<WatchlistRead[]> => {
      const accessToken = await getToken();
      const page = await listWatchlists({ accessToken });
      return page.items;
    },
    [getToken, reloadToken],
    { enabled: isLoaded && Boolean(isSignedIn) },
  );

  async function remove(item: WatchlistRead) {
    const accessToken = await getToken();
    await deleteWatchlist(item.id, { accessToken });
    setReloadToken((value) => value + 1);
  }

  if (isLoaded && !isSignedIn) {
    return <SignInRequired resource="watchlist" />;
  }
  if (!isLoaded || state.status === "idle" || state.status === "loading") {
    return <LoadingSkeleton label="Loading your watchlist" rows={4} />;
  }
  if (state.status === "error") {
    return (
      <ErrorState
        title="Watchlist could not be loaded"
        error={state.error}
        onRetry={state.reload}
      />
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-4xl text-ink">Your watchlist</h1>
        <p className="text-ink-muted">
          Only products you added appear here. Other users cannot see this list.
        </p>
      </header>
      {state.data.length === 0 ? (
        <EmptyState
          title="Your watchlist is empty"
          description="Search for a product and add it to your watchlist. Items are stored for your account only."
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
                {item.product?.slug ? (
                  <p className="text-sm text-ink-muted">{item.product.slug}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => void remove(item)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-danger hover:bg-danger-light"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
