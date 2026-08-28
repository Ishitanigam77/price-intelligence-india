"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { MetricCard } from "@/components/price/MetricCard";
import { PriceHistoryChart } from "@/components/price/PriceHistoryChart";
import { ValueKindBadge } from "@/components/price/ValueKindBadge";
import { AvailabilityBadge } from "@/components/status/AvailabilityBadge";
import { DataFreshness } from "@/components/status/DataFreshness";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { getProduct, getProductHistory } from "@/lib/api";
import { formatDateTime } from "@/lib/format/datetime";
import { formatMoneyOrUnavailable } from "@/lib/format/money";
import { formatVariant } from "@/lib/format/variant";
import { useAsync } from "@/lib/hooks/useAsync";
import type { ProductHistoryRead, ProductRead, VariantHistoryRead } from "@/lib/types/api";

interface PriceHistoryViewProps {
  productId: string;
  initialVariantId?: string;
}

interface HistoryPayload {
  product: ProductRead;
  history: ProductHistoryRead;
}

export function PriceHistoryView({ productId, initialVariantId }: PriceHistoryViewProps) {
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(
    initialVariantId ?? null,
  );
  const state = useAsync(async (): Promise<HistoryPayload> => {
    const [product, history] = await Promise.all([
      getProduct(productId),
      getProductHistory(productId, { limit: 200, offset: 0 }),
    ]);
    return { product, history };
  }, [productId]);

  const selected: VariantHistoryRead | null = useMemo(() => {
    if (state.status !== "success") {
      return null;
    }
    const variants = state.data.history.variants;
    if (selectedVariantId) {
      return (
        variants.find((item) => item.product_variant_id === selectedVariantId) ??
        variants[0] ??
        null
      );
    }
    if (initialVariantId) {
      return (
        variants.find((item) => item.product_variant_id === initialVariantId) ?? variants[0] ?? null
      );
    }
    return variants[0] ?? null;
  }, [state, selectedVariantId, initialVariantId]);

  if (state.status === "loading" || state.status === "idle") {
    return <LoadingSkeleton label="Loading price history" rows={5} />;
  }
  if (state.status === "error") {
    return (
      <ErrorState
        title="Price history could not be loaded"
        error={state.error}
        onRetry={state.reload}
      />
    );
  }

  const { product, history } = state.data;
  const observations = selected?.observations.items ?? [];
  const qualifying = observations.filter((item) => item.qualifies_for_calculations);
  const insufficientSeries = !selected || selected.qualifying_observation_count < 2;

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">Price history</p>
        <h1 className="font-display text-4xl text-ink">{product.name}</h1>
        <p className="max-w-3xl text-ink-muted">
          Price history is based on recorded prices. Forecasts are not shown.
        </p>
        <div className="flex flex-wrap gap-2">
          <ValueKindBadge kind="OBSERVED" />
          <ValueKindBadge kind="CALCULATED" />
          <ValueKindBadge kind="PREDICTED" available={false} />
        </div>
        <DataFreshness freshness={history.data_freshness} />
        <Link
          href={`/products/${product.id}${selected ? `?variant=${selected.product_variant_id}` : ""}`}
          className="inline-flex text-sm font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          Back to product details
        </Link>
      </header>

      {history.variants.length > 1 ? (
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink">Exact variant</legend>
          <div className="flex flex-wrap gap-2">
            {history.variants.map((variant) => {
              const current = variant.product_variant_id === selected?.product_variant_id;
              return (
                <button
                  key={variant.product_variant_id}
                  type="button"
                  aria-pressed={current}
                  onClick={() => setSelectedVariantId(variant.product_variant_id)}
                  className={`rounded-full px-4 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                    current ? "bg-ink text-white" : "bg-paper-muted text-ink"
                  }`}
                >
                  {formatVariant({
                    name: null,
                    attributes: {},
                    variant_key: variant.variant_key ?? variant.product_variant_id,
                  })}
                </button>
              );
            })}
          </div>
        </fieldset>
      ) : null}

      {!selected ? (
        <EmptyState
          title="No price history is available"
          description="No price history is available for this product."
        />
      ) : (
        <>
          {insufficientSeries ? (
            <EmptyState
              title="Insufficient history for a chart"
              description={
                selected.qualifying_observation_count === 0
                  ? (selected.average_7d.insufficient?.reason ??
                    "There are not enough recorded prices to calculate historical statistics.")
                  : "At least two recorded prices are required before a chart is shown."
              }
            />
          ) : (
            <PriceHistoryChart
              observations={observations}
              currency={selected.current_observation?.currency ?? "INR"}
            />
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard title="7-day average" metric={selected.average_7d} />
            <MetricCard title="30-day average" metric={selected.average_30d} />
            <MetricCard title="90-day average" metric={selected.average_90d} />
            <MetricCard title="180-day average" metric={selected.average_180d} />
            <MetricCard title="Historical low" metric={selected.historical_low} />
            <MetricCard title="Historical high" metric={selected.historical_high} />
            <MetricCard title="Current percentile" metric={selected.current_price_percentile} />
            <MetricCard title="Volatility" metric={selected.volatility} />
            <MetricCard title="Percentage change" metric={selected.percentage_change} />
            <MetricCard title="Trend" metric={selected.trend} />
          </div>

          <p className="text-sm text-ink-muted">
            {selected.qualifying_observation_count} recorded price
            {selected.qualifying_observation_count === 1 ? "" : "s"} used for calculations;{" "}
            {selected.excluded_unverified_observation_count} unverified price
            {selected.excluded_unverified_observation_count === 1 ? "" : "s"} excluded.
          </p>

          {observations.length === 0 ? (
            <EmptyState
              title="No recorded prices"
              description="No recorded prices are available for this variant."
            />
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-paper-muted bg-paper-card">
              <table className="min-w-full text-left text-sm">
                <caption className="sr-only">Observed historical prices</caption>
                <thead className="bg-paper-muted text-xs uppercase tracking-wide text-ink-muted">
                  <tr>
                    <th className="px-4 py-3">Observed at</th>
                    <th className="px-4 py-3">Retailer</th>
                    <th className="px-4 py-3">Displayed</th>
                    <th className="px-4 py-3">Effective</th>
                    <th className="px-4 py-3">Availability</th>
                    <th className="px-4 py-3">Kind</th>
                  </tr>
                </thead>
                <tbody>
                  {observations.map((item) => (
                    <tr key={item.id} className="border-t border-paper-muted">
                      <td className="px-4 py-3 whitespace-nowrap">
                        {formatDateTime(item.observed_at)}
                      </td>
                      <td className="px-4 py-3">{item.retailer_name}</td>
                      <td className="px-4 py-3 tabular-nums">
                        {formatMoneyOrUnavailable(item.displayed_price, item.currency)}
                      </td>
                      <td className="px-4 py-3 tabular-nums">
                        {formatMoneyOrUnavailable(item.effective_price, item.currency)}
                      </td>
                      <td className="px-4 py-3">
                        <AvailabilityBadge status={item.availability} />
                      </td>
                      <td className="px-4 py-3">
                        <ValueKindBadge kind="OBSERVED" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {qualifying.length === 0 && observations.length > 0 ? (
            <p className="text-sm text-ink-muted">
              Recorded prices are present, but none currently qualify for calculations.
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
