import { ValueKindBadge } from "@/components/price/ValueKindBadge";
import { cn } from "@/lib/cn";
import { formatMoneyOrUnavailable } from "@/lib/format/money";
import type { MoneyAmount, ValueKind } from "@/lib/types/api";

interface PriceDisplayProps {
  amount: MoneyAmount | null | undefined;
  currency?: string;
  kind: ValueKind;
  label: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function PriceDisplay({
  amount,
  currency = "INR",
  kind,
  label,
  size = "md",
  className,
}: PriceDisplayProps) {
  const formatted = formatMoneyOrUnavailable(amount, currency);

  return (
    <div className={cn("min-w-0", className)}>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
        <ValueKindBadge kind={kind} available={amount != null} />
      </div>
      <p
        className={cn(
          "font-display font-semibold tabular-nums tracking-tight text-price-dark",
          size === "sm" && "text-lg",
          size === "md" && "text-2xl",
          size === "lg" && "text-3xl sm:text-4xl",
          amount == null && "text-ink-muted",
        )}
      >
        {formatted}
      </p>
    </div>
  );
}
