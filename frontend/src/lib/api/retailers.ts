import { apiGet } from "@/lib/api/client";
import type { ListRetailersQuery, Page, RetailerRead, SellerRead } from "@/lib/types/api";

export function listRetailers(query?: ListRetailersQuery): Promise<Page<RetailerRead>> {
  return apiGet<Page<RetailerRead>>("/retailers", {
    active_only: query?.active_only,
    limit: query?.limit,
    offset: query?.offset,
  });
}

export function getRetailer(retailerId: string): Promise<RetailerRead> {
  return apiGet<RetailerRead>(`/retailers/${retailerId}`);
}

export function listRetailerSellers(
  retailerId: string,
  pagination?: { limit?: number; offset?: number },
): Promise<Page<SellerRead>> {
  return apiGet<Page<SellerRead>>(`/retailers/${retailerId}/sellers`, pagination);
}
