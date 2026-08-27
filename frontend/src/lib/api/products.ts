import { apiGet } from "@/lib/api/client";
import type {
  Page,
  ProductHistoryQuery,
  ProductHistoryRead,
  ProductPricesRead,
  ProductRead,
  ProductSearchPage,
  ProductVariantRead,
  SearchProductsQuery,
} from "@/lib/types/api";

export function searchProducts(query: SearchProductsQuery): Promise<ProductSearchPage> {
  return apiGet<ProductSearchPage>("/products/search", {
    q: query.q,
    category: query.category,
    limit: query.limit,
    offset: query.offset,
  });
}

export function getProduct(productId: string): Promise<ProductRead> {
  return apiGet<ProductRead>(`/products/${productId}`);
}

export function listProductVariants(
  productId: string,
  pagination?: { limit?: number; offset?: number },
): Promise<Page<ProductVariantRead>> {
  return apiGet<Page<ProductVariantRead>>(`/products/${productId}/variants`, pagination);
}

export function getProductPrices(productId: string): Promise<ProductPricesRead> {
  return apiGet<ProductPricesRead>(`/products/${productId}/prices`);
}

export function getProductHistory(
  productId: string,
  query?: ProductHistoryQuery,
): Promise<ProductHistoryRead> {
  return apiGet<ProductHistoryRead>(`/products/${productId}/history`, {
    variant_id: query?.variant_id,
    since: query?.since,
    until: query?.until,
    limit: query?.limit,
    offset: query?.offset,
  });
}
