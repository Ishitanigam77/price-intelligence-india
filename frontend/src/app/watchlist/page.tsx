import type { Metadata } from "next";

import { WatchlistView } from "@/components/watchlist/WatchlistView";

export const metadata: Metadata = {
  title: "Watchlist",
};

export const dynamic = "force-dynamic";

export default function WatchlistPage() {
  return <WatchlistView />;
}
