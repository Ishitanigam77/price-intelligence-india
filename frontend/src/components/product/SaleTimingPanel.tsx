"use client";

import { PriceDisplay } from "@/components/price/PriceDisplay";
import { ValueKindBadge } from "@/components/price/ValueKindBadge";
import { EmptyState } from "@/components/status/EmptyState";
import { formatDateTime } from "@/lib/format/datetime";
import { formatMoneyOrUnavailable } from "@/lib/format/money";
import type {
  BuyingWindow,
  ExpectedSaleWindowRead,
  ProductRecommendationRead,
  ProductSaleIntelligenceRead,
  ProductSalePricePredictionRead,
  RecommendationDecision,
  SaleOpportunityRead,
  Urgency,
  VariantSaleIntelligenceRead,
} from "@/lib/types/api";

const EVIDENCE_LABELS: Record<ExpectedSaleWindowRead["evidence_status"], string> = {
  confirmed: "Confirmed",
  expected: "Expected",
  inferred: "Inferred",
  unknown: "Unknown",
};

function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }
  return `${value}%`;
}

function opportunityCard(title: string, opportunity: SaleOpportunityRead | null) {
  if (opportunity === null || opportunity.status === "insufficient_history") {
    return (
      <EmptyState
        title={`${title} data is insufficient`}
        description="An expected price is not invented when historical evidence is thin."
      />
    );
  }
  return (
    <div className="space-y-2 rounded-xl bg-paper-muted p-4">
      <h3 className="font-display text-lg">{title}</h3>
      <p className="text-sm text-ink-muted">{opportunity.window.display_name}</p>
      <p className="text-sm">
        {opportunity.sale_type} · {EVIDENCE_LABELS[opportunity.window.evidence_status]}
      </p>
      <PriceDisplay
        label="Expected price"
        amount={opportunity.expected_price}
        currency="INR"
        kind={opportunity.expected_price_value_kind ?? "CALCULATED"}
      />
      <p className="text-sm text-ink">
        Expected saving: {formatMoneyOrUnavailable(opportunity.expected_saving)} (
        {formatPercent(opportunity.expected_saving_percentage)})
      </p>
      <p className="text-sm text-ink-muted">
        {opportunity.days_until_start ?? "Unknown"} day
        {opportunity.days_until_start === 1 ? "" : "s"} away · confidence{" "}
        {opportunity.confidence ?? "unknown"}
      </p>
      <p className="text-sm text-ink-muted">
        Likely retailer: {opportunity.likely_best_retailer_name ?? "Unknown"}
      </p>
    </div>
  );
}

function decisionCopy(decision: RecommendationDecision, window: BuyingWindow | null): string {
  if (window === "BUY_IN_ORDINARY_SALE") {
    return "The next ordinary sale is soon enough to be useful. Waiting many weeks for a major sale is not recommended when you need the product sooner.";
  }
  if (window === "WAIT_FOR_MAJOR_SALE") {
    return "Historical evidence shows a material extra saving from the major sale relative to waiting time. This is an estimate, not a guarantee.";
  }
  if (decision === "BUY_NOW") {
    return "The current verified price is already favourable on historical evidence.";
  }
  if (decision === "WAIT") {
    return "Waiting may be worthwhile based on history, an upcoming window, or a predicted saving.";
  }
  if (decision === "WATCH") {
    return "Evidence is mixed or weak, so the system does not force a buy or wait decision.";
  }
  return "There is not enough verified data for a buy-timing decision.";
}

interface SaleTimingPanelProps {
  intelligence: ProductSaleIntelligenceRead | null;
  recommendation: ProductRecommendationRead | null;
  prediction: ProductSalePricePredictionRead | null;
  variantId: string | null;
  urgency: Urgency | "";
  onUrgencyChange: (value: Urgency | "") => void;
}

export function SaleTimingPanel({
  intelligence,
  recommendation,
  prediction,
  variantId,
  urgency,
  onUrgencyChange,
}: SaleTimingPanelProps) {
  const intel: VariantSaleIntelligenceRead | undefined = intelligence?.variants.find(
    (item) => item.product_variant_id === variantId,
  );
  const rec = recommendation?.variants.find((item) => item.product_variant_id === variantId);
  const upcoming = intel?.major ?? intel?.ordinary ?? null;
  const predictedRow =
    prediction?.predictions.find((item) => item.product_variant_id === variantId) ??
    prediction?.predictions[0];

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h2 className="font-display text-2xl">Upcoming sale</h2>
        <p className="text-sm text-ink-muted">
          {intelligence?.disclaimer ??
            "Projected sale dates and prices are evidence-based estimates and are not guaranteed retailer announcements."}
        </p>
        {upcoming && upcoming.window.expected_start_date ? (
          <div className="space-y-2 rounded-2xl bg-paper-card p-5 shadow-card">
            <p className="font-medium text-ink">{upcoming.window.display_name}</p>
            <p className="text-sm">
              {upcoming.sale_type} · {EVIDENCE_LABELS[upcoming.window.evidence_status]}
            </p>
            <p className="text-sm text-ink-muted">
              Expected start {formatDateTime(upcoming.window.expected_start_date)} · expected end{" "}
              {formatDateTime(upcoming.window.expected_end_date)} · confidence{" "}
              {upcoming.window.confidence}
            </p>
          </div>
        ) : (
          <EmptyState
            title="No upcoming sale window"
            description="A sale date is not invented when evidence is insufficient."
          />
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-2xl">Predicted sale price</h2>
        <p className="flex flex-wrap gap-2 text-sm text-ink-muted">
          <ValueKindBadge kind="PREDICTED" available={predictedRow?.status === "PREDICTED"} />
        </p>
        {predictedRow?.status === "PREDICTED" && predictedRow.predicted_price != null ? (
          <div className="grid gap-4 rounded-2xl bg-paper-card p-5 shadow-card sm:grid-cols-3">
            <PriceDisplay
              label="Predicted price"
              amount={predictedRow.predicted_price}
              currency={predictedRow.currency}
              kind="PREDICTED"
            />
            <PriceDisplay
              label="Lower bound"
              amount={predictedRow.lower_bound}
              currency={predictedRow.currency}
              kind="PREDICTED"
            />
            <PriceDisplay
              label="Upper bound"
              amount={predictedRow.upper_bound}
              currency={predictedRow.currency}
              kind="PREDICTED"
            />
            <p className="text-sm text-ink-muted sm:col-span-3">
              Confidence {predictedRow.confidence ?? "unknown"}. This is an estimate, not a
              guaranteed retailer price.
            </p>
          </div>
        ) : (
          <EmptyState
            title="Predicted sale price is not available"
            description={
              prediction?.insufficient?.reason ??
              "The model artifact or history is insufficient. A predicted price is not invented."
            }
          />
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-2xl">Best expected retailer</h2>
        {intel?.expected_best_retailer && intel.expected_best_retailer.status === "available" ? (
          <div className="space-y-2 rounded-2xl bg-paper-card p-5 shadow-card">
            <p className="font-medium text-ink">{intel.expected_best_retailer.retailer_name}</p>
            <PriceDisplay
              label="Expected sale price"
              amount={intel.expected_best_retailer.expected_sale_price}
              currency="INR"
              kind={intel.expected_best_retailer.expected_sale_price_value_kind ?? "CALCULATED"}
            />
            <p className="text-sm text-ink">
              Expected saving:{" "}
              {formatMoneyOrUnavailable(intel.expected_best_retailer.expected_saving)} ·
              confidence {intel.expected_best_retailer.confidence ?? "unknown"}
            </p>
          </div>
        ) : (
          <EmptyState
            title="Expected best retailer is unknown"
            description="The currently cheapest retailer is not assumed to win a future sale."
          />
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-2xl">Ordinary vs major</h2>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-2 rounded-xl bg-paper-muted p-4">
            <h3 className="font-display text-lg">Current price</h3>
            <PriceDisplay
              label="Current verified price"
              amount={intel?.current_effective_price ?? intel?.current_cheapest_price}
              currency="INR"
              kind="CALCULATED"
            />
            <p className="text-sm text-ink-muted">
              {intel?.current_cheapest_retailer_name ?? "No verified retailer"}
            </p>
          </div>
          {opportunityCard("Ordinary sale", intel?.ordinary ?? null)}
          {opportunityCard("Major sale", intel?.major ?? null)}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-2xl">Buying recommendation</h2>
        {rec ? (
          <div className="space-y-3 rounded-2xl bg-paper-card p-5 shadow-card">
            <p className="text-xl font-semibold text-ink">{rec.recommendation}</p>
            {rec.buying_window ? (
              <p className="text-sm text-ink-muted">Buying window: {rec.buying_window}</p>
            ) : null}
            <p className="text-sm text-ink">{decisionCopy(rec.recommendation, rec.buying_window)}</p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-ink-muted">
              {rec.reasons.slice(0, 4).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <p className="text-sm text-ink-muted">{rec.disclaimer}</p>
          </div>
        ) : (
          <EmptyState
            title="Recommendation is not available"
            description="A buy/wait decision is not invented when the recommendation API cannot be loaded."
          />
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-2xl">Urgency</h2>
        <p className="text-sm text-ink-muted">
          Optional. Existing recommendations stay the same when urgency is not set.
        </p>
        <fieldset className="flex flex-wrap gap-2">
          <legend className="sr-only">Purchase urgency</legend>
          {(
            [
              ["", "No urgency"],
              ["urgent", "I need it soon"],
              ["patient", "I can wait"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={label}
              type="button"
              aria-pressed={urgency === value}
              onClick={() => onUrgencyChange(value)}
              className={`rounded-full px-4 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                urgency === value ? "bg-ink text-white" : "bg-paper-muted text-ink hover:bg-brand-light"
              }`}
            >
              {label}
            </button>
          ))}
        </fieldset>
      </section>
    </div>
  );
}
