import { apiDelete, apiGet, apiPatch, apiPost, type ApiAuth } from "@/lib/api/client";
import type { AlertRead, Page } from "@/lib/types/api";

export function listAlerts(auth?: ApiAuth): Promise<Page<AlertRead>> {
  return apiGet<Page<AlertRead>>("/alerts", { limit: 100, offset: 0 }, auth);
}

export function createAlert(
  productId: string,
  thresholdAmount: string,
  auth?: ApiAuth,
): Promise<AlertRead> {
  return apiPost<AlertRead>(
    "/alerts",
    {
      product_id: productId,
      threshold_amount: thresholdAmount,
      currency: "INR",
      is_enabled: true,
    },
    auth,
  );
}

export function updateAlert(
  itemId: string,
  payload: { is_enabled?: boolean; threshold_amount?: string },
  auth?: ApiAuth,
): Promise<AlertRead> {
  return apiPatch<AlertRead>(`/alerts/${itemId}`, payload, auth);
}

export function deleteAlert(itemId: string, auth?: ApiAuth): Promise<void> {
  return apiDelete(`/alerts/${itemId}`, auth);
}
