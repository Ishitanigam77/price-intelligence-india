import { apiDelete, apiGet, apiPost, type ApiAuth } from "@/lib/api/client";
import type { Page, TargetPriceRead } from "@/lib/types/api";

export function listTargetPrices(auth?: ApiAuth): Promise<Page<TargetPriceRead>> {
  return apiGet<Page<TargetPriceRead>>("/target-prices", { limit: 100, offset: 0 }, auth);
}

export function createTargetPrice(
  productId: string,
  amount: string,
  auth?: ApiAuth,
): Promise<TargetPriceRead> {
  return apiPost<TargetPriceRead>(
    "/target-prices",
    { product_id: productId, amount, currency: "INR" },
    auth,
  );
}

export function deleteTargetPrice(itemId: string, auth?: ApiAuth): Promise<void> {
  return apiDelete(`/target-prices/${itemId}`, auth);
}
