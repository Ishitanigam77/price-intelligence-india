import type { ValueKind } from "@/lib/types/api";
import { cn } from "@/lib/cn";

const LABELS: Record<ValueKind, string> = {
  OBSERVED: "Observed",
  CALCULATED: "Calculated",
  PREDICTED: "Predicted",
};

interface ValueKindBadgeProps {
  kind: ValueKind;
  available?: boolean;
  className?: string;
}

export function ValueKindBadge({ kind, available = true, className }: ValueKindBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        kind === "OBSERVED" && "bg-brand-light text-brand-dark",
        kind === "CALCULATED" && "bg-[#e8e7f6] text-[#3730a3]",
        kind === "PREDICTED" &&
          "border border-dashed border-ink-muted/40 bg-paper-muted text-ink-muted",
        !available && "opacity-80",
        className,
      )}
    >
      {LABELS[kind]}
      {kind === "PREDICTED" && !available ? " · not available" : null}
    </span>
  );
}
