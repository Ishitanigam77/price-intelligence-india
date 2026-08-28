import type { ProductVariantRead } from "@/lib/types/api";

export function formatVariant(
  variant: Pick<ProductVariantRead, "name" | "attributes" | "variant_key">,
): string {
  const named = variant.name?.trim();
  if (named) {
    return named;
  }
  const attributes = Object.entries(variant.attributes ?? {});
  if (attributes.length > 0) {
    return attributes.map(([key, value]) => `${humanizeKey(key)}: ${value}`).join(" · ");
  }
  if (variant.variant_key) {
    return variant.variant_key;
  }
  return "Unspecified variant";
}

function humanizeKey(key: string): string {
  return key
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
