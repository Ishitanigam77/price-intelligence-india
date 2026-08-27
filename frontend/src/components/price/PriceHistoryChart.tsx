import { formatMoney } from "@/lib/format/money";
import type { HistoryObservationRead } from "@/lib/types/api";
import { cn } from "@/lib/cn";

interface PriceHistoryChartProps {
  observations: HistoryObservationRead[];
  currency?: string;
  className?: string;
}

export function PriceHistoryChart({
  observations,
  currency = "INR",
  className,
}: PriceHistoryChartProps) {
  const points = observations
    .filter((item) => item.qualifies_for_calculations)
    .map((item) => ({
      id: item.id,
      at: new Date(item.observed_at).getTime(),
      label: item.observed_at,
      price: Number(item.analysis_price),
      retailer: item.retailer_name,
    }))
    .filter((point) => Number.isFinite(point.at) && Number.isFinite(point.price))
    .sort((a, b) => a.at - b.at);

  if (points.length < 2) {
    return null;
  }

  const minX = points[0].at;
  const maxX = points[points.length - 1].at;
  const prices = points.map((point) => point.price);
  const minY = Math.min(...prices);
  const maxY = Math.max(...prices);
  const padY = minY === maxY ? Math.max(minY * 0.05, 1) : (maxY - minY) * 0.12;
  const y0 = minY - padY;
  const y1 = maxY + padY;
  const width = 640;
  const height = 280;
  const left = 56;
  const right = 16;
  const top = 16;
  const bottom = 36;
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(y1 - y0, 1);

  const coords = points.map((point) => {
    const x = left + ((point.at - minX) / spanX) * (width - left - right);
    const y = top + ((y1 - point.price) / spanY) * (height - top - bottom);
    return { ...point, x, y };
  });
  const path = coords
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");

  return (
    <figure
      className={cn(
        "overflow-x-auto rounded-2xl border border-paper-muted bg-paper-card p-4",
        className,
      )}
    >
      <figcaption className="mb-3 text-sm text-ink-muted">
        Observed analysis prices used for historical calculations. Predicted values are not shown.
      </figcaption>
      <svg
        role="img"
        aria-labelledby="price-history-chart-title price-history-chart-desc"
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full min-w-[20rem]"
      >
        <title id="price-history-chart-title">Historical observed prices</title>
        <desc id="price-history-chart-desc">
          Line chart of qualifying observed analysis prices from {formatMoney(minY, currency)} to{" "}
          {formatMoney(maxY, currency)}.
        </desc>
        <line x1={left} y1={top} x2={left} y2={height - bottom} stroke="#cbbfaa" />
        <line
          x1={left}
          y1={height - bottom}
          x2={width - right}
          y2={height - bottom}
          stroke="#cbbfaa"
        />
        <text x={8} y={top + 4} className="fill-ink-muted" fontSize="11">
          {formatMoney(maxY, currency)}
        </text>
        <text x={8} y={height - bottom} className="fill-ink-muted" fontSize="11">
          {formatMoney(minY, currency)}
        </text>
        <path d={path} fill="none" stroke="#0f6e68" strokeWidth="2.5" />
        {coords.map((point) => (
          <circle key={point.id} cx={point.x} cy={point.y} r="4" fill="#0f6e68">
            <title>
              {point.retailer}: {formatMoney(point.price, currency)} at {point.label}
            </title>
          </circle>
        ))}
      </svg>
      <div className="sr-only">
        <table>
          <caption>Qualifying historical observations</caption>
          <thead>
            <tr>
              <th>Observed at</th>
              <th>Retailer</th>
              <th>Analysis price</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.id}>
                <td>{point.label}</td>
                <td>{point.retailer}</td>
                <td>{formatMoney(point.price, currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
