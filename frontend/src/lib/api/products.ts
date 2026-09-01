import { apiGet } from "@/lib/api/client";
import type {
  Page,
  ProductHistoryQuery,
  ProductHistoryRead,
  ProductPricesRead,
  ProductRead,
  ProductRecommendationRead,
  ProductSaleIntelligenceRead,
  ProductSalePricePredictionRead,
  ProductSearchPage,
  ProductVariantRead,
  SearchProductsQuery,
  Urgency,
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

export function getProductSaleIntelligence(
  productId: string,
  query?: { variant_id?: string },
): Promise<ProductSaleIntelligenceRead> {
  return apiGet<ProductSaleIntelligenceRead>(`/products/${productId}/sale-intelligence`, {
    variant_id: query?.variant_id,
  });
}

export function getProductRecommendation(
  productId: string,
  query?: { variant_id?: string; urgency?: Urgency },
): Promise<ProductRecommendationRead> {
  return apiGet<ProductRecommendationRead>(`/products/${productId}/recommendation`, {
    variant_id: query?.variant_id,
    urgency: query?.urgency,
  });
}

export function getProductSalePricePrediction(
  productId: string,
  query?: { variant_id?: string },
): Promise<ProductSalePricePredictionRead> {
  return apiGet<ProductSalePricePredictionRead>(
    `/products/${productId}/sale-price-prediction`,
    { variant_id: query?.variant_id },
  );
}
