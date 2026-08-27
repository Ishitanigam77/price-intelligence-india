import { formatDateTime, formatRelativeTime } from "@/lib/format/datetime";
import { cn } from "@/lib/cn";
import type { ConfidenceLevel, DataFreshnessRead, FreshnessStatus } from "@/lib/types/api";

const STATUS_LABEL: Record<FreshnessStatus, string> = {
  fresh: "Fresh",
  aging: "Aging",
  stale: "Stale",
  missing: "Missing",
};

interface DataFreshnessProps {
  freshness?: DataFreshnessRead | null;
  confidence?: ConfidenceLevel | null;
  className?: string;
}

export function DataFreshness({ freshness, confidence, className }: DataFreshnessProps) {
  const status = freshness?.status ?? "missing";
  const observed = freshness?.newest_observation ?? freshness?.observed_at ?? null;
  const relative = formatRelativeTime(observed);

  return (
    <div className={cn("flex flex-wrap items-center gap-2 text-sm text-ink-muted", className)}>
      <span
        className={cn(
          "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
          status === "fresh" && "bg-ok-light text-ok",
          status === "aging" && "bg-warn-light text-warn",
          status === "stale" && "bg-danger-light text-danger",
          status === "missing" && "bg-paper-muted text-ink-muted",
        )}
      >
        Data freshness: {STATUS_LABEL[status]}
      </span>
      {confidence ? (
        <span className="text-xs font-medium uppercase tracking-wide">
          Confidence: {confidence}
        </span>
      ) : null}
      {observed ? (
        <span>
          Last observed {formatDateTime(observed)}
          {relative ? ` (${relative})` : ""}
        </span>
      ) : (
        <span>No observation timestamp is available.</span>
      )}
    </div>
  );
}
