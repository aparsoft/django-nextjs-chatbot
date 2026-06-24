// app/components/chat/TokenUsageChart.jsx
// Lightweight bar chart for daily token usage.
// Uses pure SVG to avoid pulling in a charting dependency.

"use client";

/**
 * @param {object} props
 * @param {Array<{date: string, tokens: number, cost?: number, requests?: number}>} props.data
 * @param {string} [props.metric] - Which metric to chart: "tokens" | "cost" | "requests".
 */
export function TokenUsageChart({ data = [], metric = "tokens" }) {
  if (!data.length) {
    return (
      <p className="text-sm text-gray-500">No usage data to display.</p>
    );
  }

  const values = data.map((d) => d[metric] ?? 0);
  const max = Math.max(...values, 1);
  const barWidth = 100 / data.length;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-40 items-end gap-1">
        {data.map((d, i) => {
          const value = d[metric] ?? 0;
          const heightPct = (value / max) * 100;
          return (
            <div
              key={i}
              className="flex flex-1 flex-col items-center justify-end gap-1"
              title={`${d.date}: ${value.toLocaleString()} ${metric}`}
            >
              <div
                className="w-full rounded-t bg-blue-500 transition-all"
                style={{ height: `${heightPct}%` }}
              />
              <span className="text-[10px] text-gray-500">
                {d.date.slice(5)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-gray-500">
        Max: {max.toLocaleString()} {metric}
      </p>
    </div>
  );
}

export default TokenUsageChart;