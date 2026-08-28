import type { AvailabilityStatus } from "@/lib/types/api";

const LABELS: Record<AvailabilityStatus, string> = {
  in_stock: "In stock",
  out_of_stock: "Out of stock",
  limited_stock: "Limited stock",
  unknown: "Availability unknown",
};

export function formatAvailability(status: AvailabilityStatus): string {
  return LABELS[status] ?? LABELS.unknown;
}

export function bestAvailability(statuses: AvailabilityStatus[]): AvailabilityStatus {
  if (statuses.includes("in_stock")) {
    return "in_stock";
  }
  if (statuses.includes("limited_stock")) {
    return "limited_stock";
  }
  if (statuses.includes("out_of_stock")) {
    return "out_of_stock";
  }
  return "unknown";
}
