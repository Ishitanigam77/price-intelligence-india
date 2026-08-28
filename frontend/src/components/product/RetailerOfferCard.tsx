import Link from "next/link";

import { AvailabilityBadge } from "@/components/status/AvailabilityBadge";
import { DataFreshness } from "@/components/status/DataFreshness";
import { PriceDisplay } from "@/components/price/PriceDisplay";
import { ValueKindBadge } from "@/components/price/ValueKindBadge";
import { formatDateTime } from "@/lib/format/datetime";
import { formatMoneyOrUnavailable } from "@/lib/format/money";
import { formatAdjustmentLine, formatPriceKind, formatSourceType } from "@/lib/format/offer";
import { cn } from "@/lib/cn";
import type { ComparedOfferRead } from "@/lib/types/api";

interface RetailerOfferCardProps {
  offer: ComparedOfferRead;
  priceHistoryHref?: string;
  className?: string;
}

export function RetailerOfferCard({ offer, priceHistoryHref, className }: RetailerOfferCardProps) {
  const sellerName = offer.seller.name ?? "Seller not specified";

  return (
    <article
      className={cn(
        "flex h-full flex-col gap-4 rounded-2xl border border-paper-muted bg-paper-card p-5 shadow-card",
        offer.rank === 1 && "ring-2 ring-brand/40",
        className,
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-xl text-ink">{offer.retailer_name}</h3>
          <p className="text-sm text-ink-muted">
            Seller: {sellerName}
            {offer.seller.is_first_party ? " · First party" : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-paper-muted px-2.5 py-1 text-xs font-semibold text-ink">
            Rank {offer.rank}
          </span>
          <AvailabilityBadge status={offer.availability} />
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <PriceDisplay
          label="Displayed price"
          amount={offer.displayed_price}
          currency={offer.currency}
          kind="OBSERVED"
          size="sm"
        />
        <PriceDisplay
          label="Effective price"
          amount={offer.effective_price}
          currency={offer.currency}
          kind="CALCULATED"
          size="sm"
        />
      </div>

      {offer.unverified_estimated_price != null ? (
        <p className="rounded-xl bg-warn-light px-3 py-2 text-sm text-warn">
          Unverified estimate{" "}
          {formatMoneyOrUnavailable(offer.unverified_estimated_price, offer.currency)} is shown
          separately and is never used as the lowest verified price.
        </p>
      ) : null}

      <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-ink-muted">MRP</dt>
          <dd className="mt-1 flex items-center gap-2">
            {formatMoneyOrUnavailable(offer.mrp, offer.currency)}
            <ValueKindBadge kind="OBSERVED" />
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-ink-muted">Price type</dt>
          <dd className="mt-1 font-medium text-ink">{formatPriceKind(offer.price_kind)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-ink-muted">Observed at</dt>
          <dd className="mt-1">{formatDateTime(offer.observation_timestamp)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-ink-muted">Listing source</dt>
          <dd className="mt-1">{formatSourceType(offer.source_type)}</dd>
        </div>
      </dl>

      <DataFreshness freshness={offer.freshness} confidence={offer.confidence} />

      {offer.adjustments.length > 0 ? (
        <ul className="space-y-1 text-sm text-ink-muted">
          {offer.adjustments.map((adjustment, index) => (
            <li key={`${adjustment.kind}-${index}`}>
              {formatAdjustmentLine(adjustment, offer.currency)}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-auto flex flex-col gap-2 sm:flex-row">
        {offer.source_url ? (
          <a
            href={offer.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-brand px-4 text-sm font-semibold text-brand hover:bg-brand-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            View on retailer site
          </a>
        ) : (
          <p className="text-sm text-ink-muted">No retailer link is available for this offer.</p>
        )}
        {priceHistoryHref ? (
          <Link
            href={priceHistoryHref}
            className="inline-flex min-h-11 items-center justify-center rounded-xl bg-ink px-4 text-sm font-semibold text-white hover:bg-ink/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            View price history
          </Link>
        ) : null}
      </div>
    </article>
  );
}
