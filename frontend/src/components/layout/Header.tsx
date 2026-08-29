"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { AuthControls } from "@/components/auth/AuthControls";
import { SearchBar } from "@/components/search/SearchBar";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/deals", label: "Deals" },
  { href: "/retailers", label: "Retailers" },
  { href: "/about", label: "About" },
];

export function Header() {
  const pathname = usePathname();
  const showCompactSearch = pathname !== "/" && !pathname.startsWith("/search");

  return (
    <header className="sticky top-0 z-40 border-b border-paper-muted/80 bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-page flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:gap-6">
        <div className="flex items-center justify-between gap-4">
          <Link
            href="/"
            className="font-display text-xl tracking-tight text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            PriceRadar India
          </Link>
        </div>
        <nav aria-label="Primary" className="flex flex-wrap items-center gap-1">
          {NAV.map((item) => {
            const current = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
                  current
                    ? "bg-brand-light text-brand-dark"
                    : "text-ink-muted hover:bg-paper-muted hover:text-ink",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        {showCompactSearch ? (
          <div className="w-full lg:ml-auto lg:max-w-md">
            <SearchBar size="compact" />
          </div>
        ) : null}
        <div className="lg:ml-auto">
          <AuthControls />
        </div>
      </div>
    </header>
  );
}
