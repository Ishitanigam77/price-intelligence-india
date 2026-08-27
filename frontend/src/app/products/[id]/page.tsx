import type { Metadata } from "next";

import { ProductDetailsView } from "@/components/product/ProductDetailsView";

export const metadata: Metadata = {
  title: "Product details",
};

export default async function ProductPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ variant?: string }>;
}) {
  const { id } = await params;
  const query = await searchParams;
  return <ProductDetailsView productId={id} initialVariantId={query.variant} />;
}
