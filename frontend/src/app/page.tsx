import type { Metadata } from "next";

import { SearchBar } from "@/components/search/SearchBar";

export const metadata: Metadata = {
  title: "Home",
};

export default function HomePage() {
  return (
    <div className="overflow-x-hidden">
      <section className="rounded-3xl bg-ink px-5 py-12 text-ink-inverse sm:px-10 sm:py-16">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-brand-light">
          India-focused price intelligence
        </p>
        <h1 className="mt-3 max-w-3xl font-display text-4xl leading-tight sm:text-5xl">
          See what Indian retailers actually charged — and when they charged it.
        </h1>
        <p className="mt-4 max-w-2xl text-base text-white/75 sm:text-lg">
          Find products across Indian retailers, compare verified prices, and view price history.
          Prices are never invented or forecasted.
        </p>
        <div className="mt-8 max-w-2xl rounded-2xl bg-paper p-4 text-ink sm:p-6">
          <SearchBar autoFocus />
        </div>
      </section>

      <section className="mt-12 grid gap-6 md:grid-cols-3">
        <article className="rounded-2xl bg-paper-card p-6 shadow-card">
          <h2 className="font-display text-xl">Search products across Indian retailers</h2>
          <p className="mt-2 text-sm text-ink-muted">
            Look up a product and see matching offers from supported Indian retailers.
          </p>
        </article>
        <article className="rounded-2xl bg-paper-card p-6 shadow-card">
          <h2 className="font-display text-xl">Compare verified prices</h2>
          <p className="mt-2 text-sm text-ink-muted">
            Compare verified prices side by side. Unverified coupons and cashback never win the
            lowest verified slot.
          </p>
        </article>
        <article className="rounded-2xl bg-paper-card p-6 shadow-card">
          <h2 className="font-display text-xl">View price history</h2>
          <p className="mt-2 text-sm text-ink-muted">
            See how a product’s price has changed over time. When there is not enough history, we
            say so instead of filling in numbers.
          </p>
        </article>
      </section>
    </div>
  );
}
