"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { MetricCard } from "@/components/price/MetricCard";
import { PriceDisplay } from "@/components/price/PriceDisplay";
import { PriceHistoryChart } from "@/components/price/PriceHistoryChart";
import { ValueKindBadge } from "@/components/price/ValueKindBadge";
import { RetailerOfferCard } from "@/components/product/RetailerOfferCard";
import { AvailabilityBadge } from "@/components/status/AvailabilityBadge";
import { DataFreshness } from "@/components/status/DataFreshness";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { getProduct, getProductHistory, getProductPrices, listProductVariants } from "@/lib/api";
import { formatVariant } from "@/lib/format/variant";
import { useAsync } from "@/lib/hooks/useAsync";
import type {
  ProductHistoryRead,
  ProductPricesRead,
  ProductRead,
  ProductVariantRead,
  VariantHistoryRead,
  VariantPricesRead,
} from "@/lib/types/api";

interface ProductDetailsViewProps {
  productId: string;
  initialVariantId?: string;
}

interface DetailsPayload {
  product: ProductRead;
  variants: ProductVariantRead[];
  prices: ProductPricesRead;
  history: ProductHistoryRead;
}

function pickVariant(
  variants: ProductVariantRead[],
  prices: ProductPricesRead,
  preferred?: string,
): string | null {
  if (
    preferred &&
    (variants.some((item) => item.id === preferred) ||
      prices.variants.some((item) => item.variant_id === preferred))
  ) {
    return preferred;
  }
  return variants[0]?.id ?? prices.variants[0]?.variant_id ?? null;
}

export function ProductDetailsView({ productId, initialVariantId }: ProductDetailsViewProps) {
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(
    initialVariantId ?? null,
  );
  const state = useAsync(async (): Promise<DetailsPayload> => {
    const [product, variantPage, prices, history] = await Promise.all([
      getProduct(productId),
      listProductVariants(productId, { limit: 200, offset: 0 }),
      getProductPrices(productId),
      getProductHistory(productId, { limit: 200, offset: 0 }),
    ]);
    return { product, variants: variantPage.items, prices, history };
  }, [productId]);

  const selected = useMemo(() => {
    if (state.status !== "success") {
      return null;
    }
    const variantId = pickVariant(
      state.data.variants,
      state.data.prices,
      selectedVariantId ?? initialVariantId,
    );
    const variant = state.data.variants.find((item) => item.id === variantId) ?? null;
    const priceVariant: VariantPricesRead | undefined = state.data.prices.variants.find(
      (item) => item.variant_id === variantId,
    );
    const historyVariant: VariantHistoryRead | undefined = state.data.history.variants.find(
      (item) => item.product_variant_id === variantId,
    );
    return { variantId, variant, priceVariant, historyVariant };
  }, [state, selectedVariantId, initialVariantId]);

  if (state.status === "loading" || state.status === "idle") {
    return <LoadingSkeleton label="Loading product details" rows={5} />;
  }
  if (state.status === "error") {
    return (
      <ErrorState
        title="Product details could not be loaded"
        error={state.error}
        onRetry={state.reload}
      />
    );
  }

  const { product, variants, prices, history } = state.data;
  const lowest = selected?.priceVariant?.lowest_verified_offer ?? null;
  const offers = selected?.priceVariant?.offers ?? [];
  const historyVariant = selected?.historyVariant;

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">Product details</p>
        <h1 className="font-display text-4xl text-ink">{product.name}</h1>
        {product.description ? (
          <p className="max-w-3xl text-ink-muted">{product.description}</p>
        ) : null}
        <DataFreshness freshness={prices.data_freshness} />
      </header>

      {variants.length > 0 ? (
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink">Exact variant</legend>
          <div className="flex flex-wrap gap-2">
            {variants.map((variant) => {
              const current = variant.id === selected?.variantId;
              return (
                <button
                  key={variant.id}
                  type="button"
                  onClick={() => setSelectedVariantId(variant.id)}
                  aria-pressed={current}
                  className={`rounded-full px-4 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                    current ? "bg-ink text-white" : "bg-paper-muted text-ink hover:bg-brand-light"
                  }`}
                >
                  {formatVariant(variant)}
                </button>
              );
            })}
          </div>
        </fieldset>
      ) : (
        <p className="text-sm text-ink-muted">No variants were returned for this product.</p>
      )}

      <section className="grid gap-6 rounded-2xl bg-paper-card p-5 shadow-card lg:grid-cols-2">
        <PriceDisplay
          label="Lowest verified price"
          amount={lowest?.effective_price ?? lowest?.displayed_price}
          currency={lowest?.currency ?? "INR"}
          kind={lowest?.price_kind === "verified_effective" ? "CALCULATED" : "OBSERVED"}
          size="lg"
        />
        <div className="space-y-3">
          {lowest ? <AvailabilityBadge status={lowest.availability} /> : null}
          {selected?.priceVariant?.ranking_reason ? (
            <p className="text-sm text-ink-muted">{selected.priceVariant.ranking_reason.reason}</p>
          ) : (
            <p className="text-sm text-ink-muted">
              No verified offer is available for this variant.
            </p>
          )}
          {selected?.variant ? (
            <p className="text-sm text-ink">Exact variant: {formatVariant(selected.variant)}</p>
          ) : null}
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="font-display text-2xl">Retailer offers</h2>
          <p className="text-sm text-ink-muted">
            {offers.length} offer{offers.length === 1 ? "" : "s"} from the comparison API.
          </p>
        </div>
        {offers.length === 0 ? (
          <EmptyState
            title="No retailer offers"
            description="The comparison API returned no offers for this variant. Offers are not invented for display."
          />
        ) : (
          <ul className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {offers.map((offer) => (
              <li key={offer.offer_id}>
                <RetailerOfferCard
                  offer={offer}
                  priceHistoryHref={`/products/${product.id}/price-history?variant=${offer.variant_id}`}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="font-display text-2xl">Price history snapshot</h2>
          <Link
            href={`/products/${product.id}/price-history${selected?.variantId ? `?variant=${selected.variantId}` : ""}`}
            className="text-sm font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Open full price history
          </Link>
        </div>
        <p className="flex flex-wrap gap-2 text-sm text-ink-muted">
          <ValueKindBadge kind="OBSERVED" /> observations · <ValueKindBadge kind="CALCULATED" />{" "}
          aggregates · <ValueKindBadge kind="PREDICTED" available={false} />
        </p>
        {history.predicted !== null ? null : (
          <p className="text-sm text-ink-muted">
            Predicted prices are not returned by this API and are not displayed.
          </p>
        )}
        {historyVariant ? (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard title="7-day average" metric={historyVariant.average_7d} />
              <MetricCard title="30-day average" metric={historyVariant.average_30d} />
              <MetricCard title="Historical low" metric={historyVariant.historical_low} />
              <MetricCard title="Trend" metric={historyVariant.trend} />
            </div>
            <DataFreshness freshness={historyVariant.data_freshness} />
            <PriceHistoryChart observations={historyVariant.observations.items} />
          </>
        ) : (
          <EmptyState
            title="No history for this variant"
            description="The history API did not return a series for the selected variant."
          />
        )}
      </section>
    </div>
  );
}
