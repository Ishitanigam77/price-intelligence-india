import type { MoneyAmount } from "@/lib/types/api";

export function parseMoney(value: MoneyAmount | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  return numeric;
}

export function formatMoney(
  value: MoneyAmount | null | undefined,
  currency = "INR",
): string | null {
  const numeric = parseMoney(value);
  if (numeric === null) {
    return null;
  }
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(numeric);
  } catch {
    return `${currency} ${numeric.toLocaleString("en-IN")}`;
  }
}

export function formatMoneyOrUnavailable(
  value: MoneyAmount | null | undefined,
  currency = "INR",
  unavailable = "Not available",
): string {
  return formatMoney(value, currency) ?? unavailable;
}
