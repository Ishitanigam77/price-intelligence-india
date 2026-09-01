import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
};

export default function AboutPage() {
  return (
    <article className="prose prose-slate max-w-3xl">
      <h1 className="font-display text-4xl text-ink">About PriceRadar India</h1>
      <p className="mt-4 text-lg text-ink-muted">
        PriceRadar India is an India-focused price intelligence platform. It is designed to discover
        product listings across many Indian online retailers, keep variants distinct, and help
        people see <strong>where</strong> a configuration was offered and{" "}
        <strong>what was observed</strong> at a point in time.
      </p>
      <h2 className="mt-8 font-display text-2xl">Observed, calculated, predicted</h2>
      <p className="mt-3 text-ink-muted">
        Prices and availability on this site come from stored retailer observations. Calculated
        figures — effective price, windowed averages, historical low/high, percentile, volatility,
        percentage change, trend, and monthly statistics — are labelled as calculated. Predicted
        sale prices from the Phase 10 model are labelled predicted when a trained artifact exists;
        otherwise the UI shows insufficient data and never fabricates a number. Projected sale
        dates and prices are evidence-based estimates and are not guaranteed retailer
        announcements.
      </p>
      <h2 className="mt-8 font-display text-2xl">What is not claimed</h2>
      <p className="mt-3 text-ink-muted">
        PriceRadar does not currently operate live integrations with real consumer retailers.
        Retailer names, prices, and availability are never invented to fill empty screens.
      </p>
      <h2 className="mt-8 font-display text-2xl">Legitimate data only</h2>
      <p className="mt-3 text-ink-muted">
        When real retailers are onboarded, data collection is limited to official feeds, affiliate
        or partner programmes, and other permitted sources. The platform does not bypass CAPTCHA,
        authentication, anti-bot systems, rate limits, or retailer terms of service.
      </p>
    </article>
  );
}
