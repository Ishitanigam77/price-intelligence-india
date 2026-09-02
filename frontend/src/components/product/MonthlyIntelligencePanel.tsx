import { MetricCard } from "@/components/price/MetricCard";
import { EmptyState } from "@/components/status/EmptyState";
import type { MonthlyBucketRead, MonthlyPriceIntelligenceRead } from "@/lib/types/api";

interface MonthlyIntelligencePanelProps {
  monthly: MonthlyPriceIntelligenceRead;
}

function MonthStatsCard({ bucket, title }: { bucket: MonthlyBucketRead; title: string }) {
  return (
    <article className="space-y-3 rounded-2xl bg-paper-card p-4 shadow-card">
      <h3 className="font-display text-lg text-ink">{title}</h3>
      <p className="text-sm text-ink-muted">
        {bucket.observation_count} observation{bucket.observation_count === 1 ? "" : "s"}
        {bucket.years_used.length > 0 ? ` · years ${bucket.years_used.join(", ")}` : ""}
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <MetricCard title="Minimum" metric={bucket.minimum} />
        <MetricCard title="Average" metric={bucket.average} />
        <MetricCard title="Median" metric={bucket.median} />
        <MetricCard title="Maximum" metric={bucket.maximum} />
        <MetricCard title="Historical low" metric={bucket.historical_low} />
        <MetricCard title="Historical high" metric={bucket.historical_high} />
        <MetricCard title="Volatility" metric={bucket.volatility} />
      </div>
    </article>
  );
}

export function MonthlyIntelligencePanel({ monthly }: MonthlyIntelligencePanelProps) {
  const availableMonths = monthly.months.filter((month) => month.median.status === "available");
  const availableRetailerMonths = monthly.retailer_months.filter(
    (month) => month.median.status === "available",
  );

  if (availableMonths.length === 0) {
    return (
      <EmptyState
        title="Insufficient monthly history"
        description="Monthly averages are not invented when too few qualifying observations exist."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-paper-muted p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Best buying month
        </p>
        {monthly.best_buying_month ? (
          <p className="mt-1 text-sm text-ink">
            {monthly.best_buying_month.month_name} (CALCULATED from stored observations)
          </p>
        ) : (
          <p className="mt-1 text-sm text-ink">INSUFFICIENT HISTORY</p>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {availableMonths.map((month) => (
          <MonthStatsCard key={month.month} bucket={month} title={month.month_name} />
        ))}
      </div>
      {availableRetailerMonths.length > 0 ? (
        <div className="space-y-3">
          <h3 className="font-display text-xl text-ink">Retailer-specific monthly statistics</h3>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {availableRetailerMonths.map((month) => (
              <MonthStatsCard
                key={`${month.retailer_id}-${month.month}`}
                bucket={month}
                title={`${month.retailer_name ?? "Unknown retailer"} · ${month.month_name}`}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
