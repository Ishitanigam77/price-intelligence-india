import Link from "next/link";

export default function NotFound() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-3xl text-ink">Page not found</h1>
      <p className="text-ink-muted">That URL is not part of PriceRadar India.</p>
      <Link
        href="/"
        className="inline-flex min-h-11 items-center rounded-xl bg-brand px-4 font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        Back to home
      </Link>
    </div>
  );
}
