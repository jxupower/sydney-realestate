"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { formatPrice } from "@/lib/formatters";

interface StatPoint {
  snapshot_date: string;
  median_price?: number | null;
  rental_yield_pct?: number | null;
}

interface SuburbTrendChartProps {
  data: StatPoint[];
  metric?: "median_price" | "rental_yield_pct";
}

export function SuburbTrendChart({ data, metric = "median_price" }: SuburbTrendChartProps) {
  const sorted = [...data].sort((a, b) =>
    a.snapshot_date.localeCompare(b.snapshot_date)
  );

  const chartData = sorted.map((d) => ({
    date: d.snapshot_date.slice(0, 7), // YYYY-MM
    value: metric === "median_price" ? d.median_price : d.rental_yield_pct,
  }));

  const isPrice = metric === "median_price";

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "#9CA3AF" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#9CA3AF" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => (isPrice ? `$${(v / 1000).toFixed(0)}k` : `${v}%`)}
          width={54}
        />
        <Tooltip
          formatter={(v: number) => [isPrice ? formatPrice(v) : `${v}%`, isPrice ? "Median" : "Yield"]}
          labelStyle={{ fontSize: 11 }}
          contentStyle={{ fontSize: 11 }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="#4F46E5"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
