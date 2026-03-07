"use client";

import { Building2, TrendingUp, BarChart3, MapPin } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatScore } from "@/lib/formatters";
import { cn } from "@/components/ui/cn";

interface KpiCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  delta?: string;
  positive?: boolean;
}

function KpiCard({ icon, label, value, delta, positive }: KpiCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</span>
        <div className="w-9 h-9 bg-indigo-50 rounded-lg flex items-center justify-center text-indigo-600">
          {icon}
        </div>
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        {delta && (
          <p
            className={cn(
              "text-xs mt-0.5 font-medium",
              positive ? "text-emerald-600" : "text-red-500"
            )}
          >
            {delta}
          </p>
        )}
      </div>
    </div>
  );
}

export function KpiCards() {
  const { data: allProps } = useQuery({
    queryKey: ["properties", { status: "for_sale", limit: 1 }],
    queryFn: () => api.properties.list({ status: "for_sale", limit: 1 }),
  });

  const { data: undervalued } = useQuery({
    queryKey: ["undervalued-properties", 1000],
    queryFn: () => api.properties.undervalued(1000),
  });

  const totalActive = allProps?.total ?? 0;
  const undervaluedCount = undervalued?.total ?? 0;

  const avgScore =
    undervalued && undervalued.items.length > 0
      ? undervalued.items.reduce(
          (sum, p) => sum + (p.valuation?.underval_score_pct ?? 0),
          0
        ) / undervalued.items.length
      : null;

  // Top suburb by undervalued count
  const suburbCounts: Record<string, number> = {};
  undervalued?.items.forEach((p) => {
    if (p.address_suburb) {
      suburbCounts[p.address_suburb] = (suburbCounts[p.address_suburb] ?? 0) + 1;
    }
  });
  const topSuburb = Object.entries(suburbCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";

  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      <KpiCard
        icon={<Building2 size={18} />}
        label="Active Listings"
        value={totalActive.toLocaleString()}
      />
      <KpiCard
        icon={<TrendingUp size={18} />}
        label="Undervalued Finds"
        value={undervaluedCount.toLocaleString()}
        delta={totalActive > 0 ? `${((undervaluedCount / totalActive) * 100).toFixed(0)}% of listings` : undefined}
        positive
      />
      <KpiCard
        icon={<BarChart3 size={18} />}
        label="Avg Underval Score"
        value={avgScore != null ? formatScore(avgScore) : "—"}
        positive={avgScore != null && avgScore > 0}
      />
      <KpiCard
        icon={<MapPin size={18} />}
        label="Top Suburb"
        value={topSuburb}
        delta={topSuburb !== "—" ? `${suburbCounts[topSuburb]} opportunities` : undefined}
        positive
      />
    </div>
  );
}
