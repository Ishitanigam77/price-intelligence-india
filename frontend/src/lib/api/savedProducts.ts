import { apiDelete, apiGet, apiPost, type ApiAuth } from "@/lib/api/client";
import type { Page, SavedProductItemRead } from "@/lib/types/api";

export function listSavedProducts(auth?: ApiAuth): Promise<Page<SavedProductItemRead>> {
  return apiGet<Page<SavedProductItemRead>>("/saved-products", { limit: 100, offset: 0 }, auth);
}

export function createSavedProduct(
  productId: string,
  auth?: ApiAuth,
): Promise<SavedProductItemRead> {
  return apiPost<SavedProductItemRead>("/saved-products", { product_id: productId }, auth);
}

export function deleteSavedProduct(itemId: string, auth?: ApiAuth): Promise<void> {
  return apiDelete(`/saved-products/${itemId}`, auth);
}
