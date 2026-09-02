"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { MetricCard } from "@/components/price/MetricCard";
import { PriceDisplay } from "@/components/price/PriceDisplay";
import { PriceHistoryChart } from "@/components/price/PriceHistoryChart";
import { ValueKindBadge } from "@/components/price/ValueKindBadge";
import { MonthlyIntelligencePanel } from "@/components/product/MonthlyIntelligencePanel";
import { RetailerOfferCard } from "@/components/product/RetailerOfferCard";
import { SaleTimingPanel } from "@/components/product/SaleTimingPanel";
import { AvailabilityBadge } from "@/components/status/AvailabilityBadge";
import { DataFreshness } from "@/components/status/DataFreshness";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import {
  getProduct,
  getProductHistory,
  getProductPrices,
  getProductRecommendation,
  getProductSaleIntelligence,
  getProductSalePricePrediction,
  listProductVariants,
} from "@/lib/api";
import { formatRankingSummary } from "@/lib/format/offer";
import { formatVariant } from "@/lib/format/variant";
import { useAsync } from "@/lib/hooks/useAsync";
import type {
  ProductHistoryRead,
  ProductPricesRead,
  ProductRead,
  ProductRecommendationRead,
  ProductSaleIntelligenceRead,
  ProductSalePricePredictionRead,
  ProductVariantRead,
  Urgency,
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
  const [urgency, setUrgency] = useState<Urgency | "">("");
  const state = useAsync(async (): Promise<DetailsPayload> => {
    const [product, variantPage, prices, history] = await Promise.all([
      getProduct(productId),
      listProductVariants(productId, { limit: 200, offset: 0 }),
      getProductPrices(productId),
      getProductHistory(productId, { limit: 200, offset: 0 }),
    ]);
    return { product, variants: variantPage.items, prices, history };
  }, [productId]);

  const timingState = useAsync(
    async (): Promise<{
      intelligence: ProductSaleIntelligenceRead;
      recommendation: ProductRecommendationRead;
      prediction: ProductSalePricePredictionRead;
    }> => {
      const [intelligence, recommendation, prediction] = await Promise.all([
        getProductSaleIntelligence(productId),
        getProductRecommendation(productId, { urgency: urgency || undefined }),
        getProductSalePricePrediction(productId),
      ]);
      return { intelligence, recommendation, prediction };
    },
    [productId, urgency],
  );

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
        <p className="text-sm text-ink-muted">No variants are available for this product.</p>
      )}

      <section className="grid gap-6 rounded-2xl bg-paper-card p-5 shadow-card lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="font-display text-2xl">Current best price</h2>
          <PriceDisplay
            label="Lowest verified price"
            amount={lowest?.effective_price ?? lowest?.displayed_price}
            currency={lowest?.currency ?? "INR"}
            kind={lowest?.price_kind === "verified_effective" ? "CALCULATED" : "OBSERVED"}
            size="lg"
          />
        </div>
        <div className="space-y-3">
          {lowest ? <AvailabilityBadge status={lowest.availability} /> : null}
          <p className="text-sm text-ink">
            Current best retailer: {lowest?.retailer_name ?? "NOT_AVAILABLE"}
          </p>
          <p className="text-sm text-ink-muted">
            {formatRankingSummary(selected?.priceVariant?.ranking_reason)}
          </p>
          {selected?.variant ? (
            <p className="text-sm text-ink">Exact variant: {formatVariant(selected.variant)}</p>
          ) : null}
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl">All retailer offers</h2>
            <p className="text-sm text-ink-muted">
              A retailer is a store identity. A seller/listing is one offer on that store. Multiple
              sellers on the same retailer still count as one retailer.
            </p>
          </div>
          <p className="text-sm text-ink-muted">
            {selected?.priceVariant?.distinct_retailer_count ?? 0} distinct retailer
            {(selected?.priceVariant?.distinct_retailer_count ?? 0) === 1 ? "" : "s"} ·{" "}
            {selected?.priceVariant?.offer_count ?? offers.length} offer
            {(selected?.priceVariant?.offer_count ?? offers.length) === 1 ? "" : "s"}.
          </p>
        </div>
        {offers.length === 0 ? (
          <EmptyState
            title="No retailer offers yet."
            description="Offers are not invented for display."
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
          <h2 className="font-display text-2xl">Current price intelligence</h2>
          <Link
            href={`/products/${product.id}/price-history${selected?.variantId ? `?variant=${selected.variantId}` : ""}`}
            className="text-sm font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Open full price history
          </Link>
        </div>
        <p className="text-sm text-ink-muted">
          Window averages, extrema, and trend are CALCULATED by the backend from stored
          PriceSnapshot rows via GET /api/v1/products/{"{id}"}/history. The browser formats
          those fields for display and does not average, min/max, or trend prices itself.
        </p>
        <p className="flex flex-wrap gap-2 text-sm text-ink-muted">
          <ValueKindBadge kind="OBSERVED" /> observations · <ValueKindBadge kind="CALCULATED" />{" "}
          aggregates · <ValueKindBadge kind="PREDICTED" available={false} />
        </p>
        {history.predicted !== null ? null : (
          <p className="text-sm text-ink-muted">Price predictions are not available.</p>
        )}
        {historyVariant ? (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <MetricCard title="7-day average" metric={historyVariant.average_7d} />
              <MetricCard title="30-day average" metric={historyVariant.average_30d} />
              <MetricCard title="90-day average" metric={historyVariant.average_90d} />
              <MetricCard title="180-day average" metric={historyVariant.average_180d} />
              <MetricCard title="Historical low" metric={historyVariant.historical_low} />
              <MetricCard title="Historical high" metric={historyVariant.historical_high} />
              <MetricCard title="Trend" metric={historyVariant.trend} />
            </div>
            <DataFreshness freshness={historyVariant.data_freshness} />
            <PriceHistoryChart observations={historyVariant.observations.items} />
          </>
        ) : (
          <EmptyState
            title="No price history is available for this variant."
            description="Price history is never invented for display."
          />
        )}
      </section>

      <section className="space-y-4">
        <h2 className="font-display text-2xl">Monthly price intelligence</h2>
        <p className="text-sm text-ink-muted">
          Calculated from stored observations by calendar month. This does not replace 7/30/90/180-day
          history and is not a forecast.
        </p>
        {historyVariant?.monthly ? (
          <MonthlyIntelligencePanel monthly={historyVariant.monthly} />
        ) : (
          <EmptyState
            title="Monthly price intelligence is not available"
            description="Monthly statistics are never fabricated for display."
          />
        )}
      </section>

      {timingState.status === "loading" || timingState.status === "idle" ? (
        <LoadingSkeleton label="Loading sale timing intelligence" rows={4} />
      ) : timingState.status === "error" ? (
        <ErrorState
          title="Sale timing intelligence could not be loaded"
          error={timingState.error}
          onRetry={timingState.reload}
        />
      ) : (
        <SaleTimingPanel
          intelligence={timingState.data.intelligence}
          recommendation={timingState.data.recommendation}
          prediction={timingState.data.prediction}
          variantId={selected?.variantId ?? null}
          urgency={urgency}
          onUrgencyChange={setUrgency}
        />
      )}
    </div>
  );
}
