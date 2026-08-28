import { formatAvailability } from "@/lib/format/availability";
import { cn } from "@/lib/cn";
import type { AvailabilityStatus } from "@/lib/types/api";

interface AvailabilityBadgeProps {
  status: AvailabilityStatus;
  className?: string;
}

export function AvailabilityBadge({ status, className }: AvailabilityBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
        status === "in_stock" && "bg-ok-light text-ok",
        status === "limited_stock" && "bg-warn-light text-warn",
        status === "out_of_stock" && "bg-danger-light text-danger",
        status === "unknown" && "bg-paper-muted text-ink-muted",
        className,
      )}
    >
      {formatAvailability(status)}
    </span>
  );
}
