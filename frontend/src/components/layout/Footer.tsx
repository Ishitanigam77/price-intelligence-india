import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-paper-muted bg-ink text-ink-inverse">
      <div className="mx-auto grid max-w-page gap-8 px-4 py-10 sm:grid-cols-2 sm:px-6 lg:grid-cols-3">
        <div>
          <p className="font-display text-lg">PriceRadar India</p>
          <p className="mt-2 text-sm text-white/70">
            Price intelligence from observed retailer data. Displayed prices are facts recorded at a
            point in time. Calculated figures are labelled. This release does not include price
            predictions.
          </p>
        </div>
        <div>
          <p className="text-sm font-semibold">Explore</p>
          <ul className="mt-2 space-y-2 text-sm">
            <li>
              <Link
                className="underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                href="/"
              >
                Search
              </Link>
            </li>
            <li>
              <Link
                className="underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                href="/deals"
              >
                Deals
              </Link>
            </li>
            <li>
              <Link
                className="underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                href="/retailers"
              >
                Retailers
              </Link>
            </li>
            <li>
              <Link
                className="underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                href="/about"
              >
                About
              </Link>
            </li>
            <li>
              <Link
                className="underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                href="/watchlist"
              >
                Watchlist
              </Link>
            </li>
            <li>
              <Link
                className="underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                href="/alerts"
              >
                Alerts
              </Link>
            </li>
            <li>
              <Link
                className="underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                href="/profile"
              >
                Profile
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold">Data integrity</p>
          <p className="mt-2 text-sm text-white/70">
            This release does not claim live marketplace integrations. Prices are never invented.
          </p>
        </div>
      </div>
    </footer>
  );
}
