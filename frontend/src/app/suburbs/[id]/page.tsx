"use client";

import { use } from "react";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { PageShell } from "@/components/layout/PageShell";
import { SuburbTrendChart } from "@/components/suburb/SuburbTrendChart";
import { PropertyRow } from "@/components/property/PropertyRow";
import { useSuburb, useSuburbStats } from "@/hooks/useSuburbs";
import { useProperties } from "@/hooks/useProperties";
import { formatPrice } from "@/lib/formatters";
import { useState } from "react";
import { PropertyDetailDrawer } from "@/components/property/PropertyDetailDrawer";
import type { PropertySummary } from "@/lib/api";

export default function SuburbDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const suburbId = Number(id);
  const [selectedProperty, setSelectedProperty] = useState<PropertySummary | null>(null);

  const { data: suburb, isLoading } = useSuburb(suburbId);
  const { data: statsHistory } = useSuburbStats(suburbId);
  const { data: properties } = useProperties({ limit: 10, sort_by: "listed_at", sort_dir: "desc" });

  if (isLoading) {
    return (
      <PageShell title="Suburb Detail">
        <div className="text-sm text-gray-400">Loading…</div>
      </PageShell>
    );
  }

  if (!suburb) {
    return (
      <PageShell title="Suburb Not Found">
        <p className="text-sm text-gray-500">This suburb does not exist.</p>
      </PageShell>
    );
  }

  const stats = suburb.stats;
  const history = Array.isArray(statsHistory) ? statsHistory : [];

  return (
    <PageShell title={suburb.name}>
      <div className="max-w-5xl mx-auto">
        <Link
          href="/suburbs"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-indigo-600 mb-4 transition-colors"
        >
          <ArrowLeft size={14} />
          Back to Suburbs
        </Link>

        {/* Stats cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { label: "Median Price", value: stats?.median_price ? formatPrice(stats.median_price) : "—" },
            { label: "1yr Growth", value: stats?.capital_growth_1yr != null ? `${stats.capital_growth_1yr > 0 ? "+" : ""}${stats.capital_growth_1yr.toFixed(1)}%` : "—" },
            { label: "3yr Growth", value: stats?.capital_growth_3yr != null ? `${stats.capital_growth_3yr > 0 ? "+" : ""}${stats.capital_growth_3yr.toFixed(1)}%` : "—" },
            { label: "Rental Yield", value: stats?.rental_yield_pct != null ? `${stats.rental_yield_pct.toFixed(1)}%` : "—" },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500 mb-1">{label}</p>
              <p className="text-xl font-bold text-gray-900">{value}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* Trend chart */}
          <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Median Price Trend</h2>
            {history.length > 0 ? (
              <SuburbTrendChart data={history as Parameters<typeof SuburbTrendChart>[0]["data"]} metric="median_price" />
            ) : (
              <div className="h-48 flex items-center justify-center text-sm text-gray-400">
                No historical data available.
              </div>
            )}
          </div>

          {/* Details */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Details</h2>
            <div className="space-y-2 text-sm">
              {[
                ["Suburb", suburb.name],
                ["Postcode", suburb.postcode],
                ["LGA", suburb.lga],
                ["Snapshot", stats?.snapshot_date?.slice(0, 10)],
              ].map(([label, value]) =>
                value ? (
                  <div key={label as string} className="flex justify-between">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-medium">{value}</span>
                  </div>
                ) : null
              )}
            </div>
          </div>
        </div>

        {/* Recent listings */}
        {properties && properties.items.length > 0 && (
          <div className="mt-6 bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-900">Recent Listings Nearby</h2>
            </div>
            {properties.items.slice(0, 5).map((p) => (
              <PropertyRow key={p.id} property={p} onClick={setSelectedProperty} />
            ))}
          </div>
        )}
      </div>

      <PropertyDetailDrawer
        property={selectedProperty}
        onClose={() => setSelectedProperty(null)}
      />
    </PageShell>
  );
}
