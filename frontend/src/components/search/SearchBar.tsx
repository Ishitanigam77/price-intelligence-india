"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useId, useState } from "react";

import { cn } from "@/lib/cn";

interface SearchBarProps {
  initialQuery?: string;
  autoFocus?: boolean;
  size?: "hero" | "compact";
  className?: string;
}

export function SearchBar({
  initialQuery = "",
  autoFocus = false,
  size = "hero",
  className,
}: SearchBarProps) {
  const router = useRouter();
  const inputId = useId();
  const errorId = useId();
  const [query, setQuery] = useState(initialQuery);
  const [error, setError] = useState<string | null>(null);
  const isHero = size === "hero";

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = query.trim();
    if (!text) {
      setError("Enter a product name to search.");
      return;
    }
    if (text.length > 500) {
      setError("Search text must be 500 characters or fewer.");
      return;
    }
    setError(null);
    router.push(`/search?q=${encodeURIComponent(text)}`);
  }

  return (
    <form
      onSubmit={onSubmit}
      role="search"
      className={cn("w-full", className)}
      aria-describedby={error ? errorId : undefined}
    >
      <label
        htmlFor={inputId}
        className={cn(
          "block font-medium text-ink",
          isHero ? "mb-2 text-base sm:text-lg" : "sr-only",
        )}
      >
        Search products across Indian retailers
      </label>
      <div
        className={cn(
          "flex w-full flex-col gap-2 sm:flex-row sm:items-stretch",
          isHero ? "sm:gap-3" : "sm:gap-2",
        )}
      >
        <input
          id={inputId}
          name="q"
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            if (error) {
              setError(null);
            }
          }}
          autoFocus={autoFocus}
          autoComplete="off"
          maxLength={500}
          placeholder="Search products across Indian retailers"
          className={cn(
            "w-full rounded-xl border border-paper-muted bg-paper-card text-ink shadow-sm",
            "placeholder:text-ink-muted/80",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
            isHero ? "min-h-14 px-4 text-base sm:text-lg" : "min-h-11 px-3 text-sm",
          )}
        />
        <button
          type="submit"
          className={cn(
            "inline-flex shrink-0 items-center justify-center rounded-xl bg-brand font-semibold text-white",
            "hover:bg-brand-dark",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
            isHero ? "min-h-14 px-6 text-base" : "min-h-11 px-4 text-sm",
          )}
        >
          Search
        </button>
      </div>
      {error ? (
        <p id={errorId} role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {isHero ? (
        <p className="mt-3 text-sm text-ink-muted">
          Compare prices from supported Indian retailers.{" "}
          <Link
            href="/about"
            className="font-medium text-brand underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            How PriceRadar uses data
          </Link>
        </p>
      ) : null}
    </form>
  );
}
