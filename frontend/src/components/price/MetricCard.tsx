import { ValueKindBadge } from "@/components/price/ValueKindBadge";
import { formatMoneyOrUnavailable } from "@/lib/format/money";
import { cn } from "@/lib/cn";
import type { CalculatedMetricRead, ExtremaMetricRead, TrendRead } from "@/lib/types/api";

interface MetricCardProps {
  title: string;
  metric: CalculatedMetricRead | ExtremaMetricRead | TrendRead;
  currency?: string;
  className?: string;
}

function isTrend(metric: MetricCardProps["metric"]): metric is TrendRead {
  return "direction" in metric;
}

export function MetricCard({ title, metric, currency = "INR", className }: MetricCardProps) {
  const insufficient = metric.status === "insufficient_history";
  let valueLabel = "Not available";
  if (isTrend(metric)) {
    valueLabel = metric.direction.replaceAll("_", " ");
  } else if (!insufficient && metric.value != null) {
    const unit = "unit" in metric ? metric.unit : "";
    valueLabel =
      unit === "percent" || unit === "%" || unit === "percentile"
        ? `${metric.value}${unit === "percentile" ? "" : "%"}`
        : unit === "ratio"
          ? String(metric.value)
          : formatMoneyOrUnavailable(metric.value, currency);
  }

  return (
    <article
      className={cn(
        "rounded-2xl border border-paper-muted bg-paper-card p-4",
        insufficient && "border-dashed",
        className,
      )}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-ink">{title}</h3>
        <ValueKindBadge kind="CALCULATED" />
      </div>
      <p className={cn("font-display text-xl text-ink", insufficient && "text-ink-muted")}>
        {insufficient ? "Insufficient history" : valueLabel}
      </p>
      {insufficient && metric.insufficient ? (
        <p className="mt-2 text-xs text-ink-muted">{metric.insufficient.reason}</p>
      ) : (
        <p className="mt-2 text-xs text-ink-muted">
          {metric.observation_count} qualifying observation
          {metric.observation_count === 1 ? "" : "s"}
        </p>
      )}
    </article>
  );
}
