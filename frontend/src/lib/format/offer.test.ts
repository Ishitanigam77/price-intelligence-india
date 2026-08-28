import { describe, expect, it } from "vitest";

import {
  formatAdjustmentLine,
  formatPriceKind,
  formatRankingSummary,
  formatSourceType,
} from "@/lib/format/offer";
import type { PriceAdjustmentRead, RankingReasonRead } from "@/lib/types/api";

describe("offer shopper labels", () => {
  it("maps source types without exposing API terminology", () => {
    expect(formatSourceType("official_api")).toBe("Official retailer listing");
    expect(formatSourceType("affiliate_feed")).toBe("Partner listing");
    expect(formatSourceType(null)).toBe("Not provided");
  });

  it("maps price kinds without exposing enum names", () => {
    expect(formatPriceKind("displayed_only")).toBe("Listed price");
    expect(formatPriceKind("verified_effective")).toBe("Verified price");
    expect(formatPriceKind("estimated_unverified")).toBe("Unverified estimate");
  });

  it("summarises ranking from the criterion instead of raw backend reasons", () => {
    const ranking: RankingReasonRead = {
      criterion: "displayed_price",
      reason: "Only available offer; ranking fell back to displayed price INR 59999.00",
      tie_breakers_applied: [],
      selected_offer_id: "offer-1",
    };
    expect(formatRankingSummary(ranking)).not.toMatch(/ranking fell back/i);
    expect(formatRankingSummary(ranking)).toMatch(/lowest listed price/i);
    expect(formatRankingSummary(null)).toBe("No verified offer is available for this variant.");
  });

  it("describes adjustments without developer field names", () => {
    const adjustment: PriceAdjustmentRead = {
      kind: "displayed_discount",
      amount: "10000.00",
      source: "listing",
      eligibility: "verified_eligible",
      observed_at: "2026-08-27T16:00:00Z",
      confidence: "high",
      affects_effective_price: true,
    };
    const line = formatAdjustmentLine(adjustment, "INR");
    expect(line).toMatch(/Listed discount/);
    expect(line).toMatch(/Verified/);
    expect(line).toMatch(/included in the price you would pay/);
    expect(line).not.toMatch(/displayed discount/i);
    expect(line).not.toMatch(/verified eligible/i);
    expect(line).not.toMatch(/affects effective price/i);
  });
});
