import Link from "next/link";

import { AvailabilityBadge } from "@/components/status/AvailabilityBadge";
import { PriceDisplay } from "@/components/price/PriceDisplay";
import { ValueKindBadge } from "@/components/price/ValueKindBadge";
import { formatDateTime } from "@/lib/format/datetime";
import { formatMoney } from "@/lib/format/money";
import { formatVariant } from "@/lib/format/variant";
import type { GroupedSearchCard } from "@/lib/search/groupHits";
import { cn } from "@/lib/cn";
import type { ValueKind } from "@/lib/types/api";

interface ProductCardProps {
  card: GroupedSearchCard;
  className?: string;
}

function verifiedKind(card: GroupedSearchCard): ValueKind {
  const kind = card.lowestVerifiedOffer?.price_kind;
  if (kind === "verified_effective") {
    return "CALCULATED";
  }
  return "OBSERVED";
}

function verifiedAmount(card: GroupedSearchCard) {
  const offer = card.lowestVerifiedOffer;
  if (!offer) {
    return null;
  }
  if (offer.price_kind === "verified_effective") {
    return offer.effective_price ?? offer.displayed_price;
  }
  return offer.displayed_price;
}

export function ProductCard({ card, className }: ProductCardProps) {
  const detailsHref = `/products/${card.product.id}?variant=${card.variant.id}`;
  const min = formatMoney(card.observedMinPrice, card.currency);
  const max = formatMoney(card.observedMaxPrice, card.currency);
  const sameRange = min === max;
  const rangeLabel = min && max ? (sameRange ? min : `${min} – ${max}`) : "Not available";

  return (
    <article
      className={cn(
        "flex h-full flex-col overflow-hidden rounded-2xl border border-paper-muted bg-paper-card shadow-card",
        className,
      )}
    >
      <div
        className="flex min-h-40 items-center justify-center bg-paper-muted px-4 py-8 text-center"
        role="img"
        aria-label={`${card.product.name}: no product photo available`}
      >
        <p className="text-sm text-ink-muted">
          No product photo available.
          <span className="mt-1 block text-xs">Placeholder — not a retailer photo.</span>
        </p>
      </div>
      <div className="flex flex-1 flex-col gap-4 p-5">
        <div>
          <h2 className="font-display text-xl leading-snug text-ink">
            <Link
              href={detailsHref}
              className="hover:text-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              {card.product.name}
            </Link>
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Exact variant: {formatVariant(card.variant)}
          </p>
        </div>
        <PriceDisplay
          label="Lowest verified price"
          amount={verifiedAmount(card) ?? card.observedMinPrice}
          currency={card.lowestVerifiedOffer?.currency ?? card.currency}
          kind={card.lowestVerifiedOffer ? verifiedKind(card) : "OBSERVED"}
          size="md"
        />
        {!card.lowestVerifiedOffer ? (
          <p className="text-xs text-ink-muted">
            Showing the lowest observed displayed price from this search. A verified comparison was
            not available for this variant.
          </p>
        ) : null}
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Retailers</dt>
            <dd className="mt-1 font-medium text-ink">{card.retailerCount}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Observed price range</dt>
            <dd className="mt-1 flex flex-wrap items-center gap-2 font-medium text-ink">
              {rangeLabel}
              <ValueKindBadge kind="OBSERVED" />
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Availability</dt>
            <dd className="mt-1">
              <AvailabilityBadge status={card.availability} />
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Last updated</dt>
            <dd className="mt-1 font-medium text-ink">{formatDateTime(card.lastUpdated)}</dd>
          </div>
        </dl>
        <Link
          href={detailsHref}
          className="mt-auto inline-flex min-h-11 items-center justify-center rounded-xl bg-brand px-4 text-sm font-semibold text-white hover:bg-brand-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          View product details
        </Link>
      </div>
    </article>
  );
}
