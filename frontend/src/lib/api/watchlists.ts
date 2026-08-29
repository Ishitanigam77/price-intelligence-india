import { apiDelete, apiGet, apiPost, type ApiAuth } from "@/lib/api/client";
import type { Page, WatchlistRead } from "@/lib/types/api";

export function listWatchlists(auth?: ApiAuth): Promise<Page<WatchlistRead>> {
  return apiGet<Page<WatchlistRead>>("/watchlists", { limit: 100, offset: 0 }, auth);
}

export function createWatchlist(productId: string, auth?: ApiAuth): Promise<WatchlistRead> {
  return apiPost<WatchlistRead>("/watchlists", { product_id: productId }, auth);
}

export function deleteWatchlist(itemId: string, auth?: ApiAuth): Promise<void> {
  return apiDelete(`/watchlists/${itemId}`, auth);
}
