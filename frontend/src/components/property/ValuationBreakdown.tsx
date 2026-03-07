"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { formatPrice } from "@/lib/formatters";
import type { ValuationDetail } from "@/lib/api";

interface ValuationBreakdownProps {
  listPrice: number | null;
  valuation: ValuationDetail | null | undefined;
}

export function ValuationBreakdown({ listPrice, valuation }: ValuationBreakdownProps) {
  if (!valuation) {
    return (
      <div className="text-sm text-gray-400 text-center py-4">
        No ML valuation available yet.
      </div>
    );
  }

  const predicted = valuation.predicted_value_cents ?? null;
  const score = valuation.underval_score_pct ?? null;
  const ciLow = valuation.confidence_interval_low;
  const ciHigh = valuation.confidence_interval_high;
  const scorePositive = score != null && score > 0;

  const shap = valuation.feature_importances;
  const shapData = shap
    ? Object.entries(shap)
        .map(([feature, value]) => ({ feature: feature.replace(/_/g, " "), value }))
        .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
        .slice(0, 10)
    : [];

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Listed at</span>
          <span className="font-medium">{formatPrice(listPrice)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">ML Estimate</span>
          <span className="font-semibold text-gray-900">{formatPrice(predicted)}</span>
        </div>
        {ciLow != null && ciHigh != null && (
          <div className="flex justify-between text-xs text-gray-400">
            <span>Confidence range</span>
            <span>
              {formatPrice(ciLow)} – {formatPrice(ciHigh)}
            </span>
          </div>
        )}
        {score != null && (
          <div
            className={`flex justify-between text-sm font-semibold ${
              scorePositive ? "text-emerald-600" : "text-red-600"
            }`}
          >
            <span>{scorePositive ? "Undervalued by" : "Overvalued by"}</span>
            <span>
              {scorePositive ? "+" : ""}
              {score.toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      {shapData.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Key Factors
          </p>
          <ResponsiveContainer width="100%" height={Math.max(180, shapData.length * 20)}>
            <BarChart
              data={shapData}
              layout="vertical"
              margin={{ left: 8, right: 8, top: 0, bottom: 0 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="feature"
                width={110}
                tick={{ fontSize: 10, fill: "#6B7280" }}
              />
              <Tooltip
                formatter={(v: number) => [
                  `${v > 0 ? "+" : ""}${(v / 100).toFixed(1)}%`,
                  "Impact",
                ]}
                contentStyle={{ fontSize: 11 }}
              />
              <Bar dataKey="value" radius={2}>
                {shapData.map((entry, i) => (
                  <Cell key={i} fill={entry.value >= 0 ? "#10B981" : "#EF4444"} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-gray-400 mt-1 text-center">
            SHAP feature contributions (green = adds value)
          </p>
        </div>
      )}

      {valuation.model_version && (
        <p className="text-xs text-gray-300 text-right">Model: {valuation.model_version}</p>
      )}
    </div>
  );
}
