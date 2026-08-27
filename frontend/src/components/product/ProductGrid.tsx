import { ProductCard } from "@/components/product/ProductCard";
import type { GroupedSearchCard } from "@/lib/search/groupHits";
import { cn } from "@/lib/cn";

interface ProductGridProps {
  cards: GroupedSearchCard[];
  className?: string;
}

export function ProductGrid({ cards, className }: ProductGridProps) {
  return (
    <ul className={cn("grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3", className)}>
      {cards.map((card) => (
        <li key={`${card.product.id}-${card.variant.id}`}>
          <ProductCard card={card} />
        </li>
      ))}
    </ul>
  );
}
