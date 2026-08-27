import type { Metadata } from "next";

import { PriceHistoryView } from "@/components/price/PriceHistoryView";

export const metadata: Metadata = {
  title: "Price history",
};

export default async function PriceHistoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ variant?: string }>;
}) {
  const { id } = await params;
  const query = await searchParams;
  return <PriceHistoryView productId={id} initialVariantId={query.variant} />;
}
