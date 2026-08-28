import { apiGet } from "@/lib/api/client";
import type { DealRead, Page, PaginationQuery } from "@/lib/types/api";

export function listDeals(query?: PaginationQuery): Promise<Page<DealRead>> {
  return apiGet<Page<DealRead>>("/deals", {
    limit: query?.limit,
    offset: query?.offset,
  });
}
