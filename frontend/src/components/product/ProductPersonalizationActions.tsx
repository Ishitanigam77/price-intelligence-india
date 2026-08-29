"use client";

import { SignedIn, SignedOut, SignInButton, useAuth } from "@clerk/nextjs";
import { FormEvent, useState } from "react";

import { createAlert } from "@/lib/api/alerts";
import { ApiError } from "@/lib/api/errors";
import { createSavedProduct } from "@/lib/api/savedProducts";
import { createTargetPrice } from "@/lib/api/targetPrices";
import { createWatchlist } from "@/lib/api/watchlists";
import { isClerkConfigured } from "@/lib/auth/config";

interface ProductPersonalizationActionsProps {
  productId: string;
}

export function ProductPersonalizationActions({ productId }: ProductPersonalizationActionsProps) {
  if (!isClerkConfigured()) {
    return null;
  }
  return <AuthenticatedProductActions productId={productId} />;
}

function AuthenticatedProductActions({ productId }: ProductPersonalizationActionsProps) {
  const { getToken } = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(label: string, action: (token: string | null) => Promise<unknown>) {
    setError(null);
    setMessage(null);
    try {
      const accessToken = await getToken();
      await action(accessToken);
      setMessage(label);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError("Already saved for your account.");
        return;
      }
      setError(caught instanceof Error ? caught.message : "The request failed.");
    }
  }

  async function onTargetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = String(new FormData(event.currentTarget).get("amount") ?? "").trim();
    if (!amount) {
      setError("Enter a target price amount.");
      return;
    }
    await run("Target price saved.", (token) =>
      createTargetPrice(productId, amount, { accessToken: token }),
    );
  }

  async function onAlertSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = String(new FormData(event.currentTarget).get("threshold") ?? "").trim();
    if (!amount) {
      setError("Enter an alert threshold.");
      return;
    }
    await run("Alert created.", (token) => createAlert(productId, amount, { accessToken: token }));
  }

  return (
    <section className="mt-8 space-y-4 rounded-2xl border border-paper-muted bg-paper-card p-5 shadow-card">
      <h2 className="font-display text-2xl text-ink">Save for your account</h2>
      <SignedOut>
        <p className="text-sm text-ink-muted">
          Sign in to watch, save, or set a target price for this product.
        </p>
        <SignInButton mode="redirect">
          <button
            type="button"
            className="inline-flex min-h-11 items-center rounded-xl bg-brand px-4 text-sm font-semibold text-white"
          >
            Sign in
          </button>
        </SignInButton>
      </SignedOut>
      <SignedIn>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() =>
              void run("Added to watchlist.", (token) =>
                createWatchlist(productId, { accessToken: token }),
              )
            }
            className="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-dark"
          >
            Add to watchlist
          </button>
          <button
            type="button"
            onClick={() =>
              void run("Product saved.", (token) =>
                createSavedProduct(productId, { accessToken: token }),
              )
            }
            className="rounded-xl bg-paper-muted px-4 py-2 text-sm font-semibold text-ink hover:bg-brand-light"
          >
            Save product
          </button>
        </div>
        <form
          onSubmit={(event) => void onTargetSubmit(event)}
          className="flex flex-wrap items-end gap-2"
        >
          <label className="text-sm">
            <span className="mb-1 block font-medium text-ink">Target price (INR)</span>
            <input
              name="amount"
              inputMode="decimal"
              className="rounded-xl border border-paper-muted px-3 py-2"
            />
          </label>
          <button
            type="submit"
            className="rounded-xl bg-paper-muted px-4 py-2 text-sm font-semibold text-ink"
          >
            Save target
          </button>
        </form>
        <form
          onSubmit={(event) => void onAlertSubmit(event)}
          className="flex flex-wrap items-end gap-2"
        >
          <label className="text-sm">
            <span className="mb-1 block font-medium text-ink">Alert threshold (INR)</span>
            <input
              name="threshold"
              inputMode="decimal"
              className="rounded-xl border border-paper-muted px-3 py-2"
            />
          </label>
          <button
            type="submit"
            className="rounded-xl bg-paper-muted px-4 py-2 text-sm font-semibold text-ink"
          >
            Create alert
          </button>
        </form>
        {message ? <p className="text-sm text-brand-dark">{message}</p> : null}
        {error ? <p className="text-sm text-danger">{error}</p> : null}
      </SignedIn>
    </section>
  );
}
