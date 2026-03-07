"use client";

import lazyLoad from "next/dynamic";
import { Suspense, useState } from "react";
import { useQueryState, parseAsString, parseAsInteger, parseAsFloat } from "nuqs";
import { PageShell } from "@/components/layout/PageShell";
import { KpiCards } from "@/components/dashboard/KpiCards";
import { FilterBar } from "@/components/filters/FilterBar";
import { PropertyList } from "@/components/property/PropertyList";
import { PropertyDetailDrawer } from "@/components/property/PropertyDetailDrawer";
import { useProperties } from "@/hooks/useProperties";
import { useMapStore, boundsTobbox } from "@/store/mapStore";
import type { PropertySummary } from "@/lib/api";

const PropertyMap = lazyLoad(
  () => import("@/components/map/PropertyMap").then((m) => m.PropertyMap),
  { ssr: false, loading: () => <div className="h-full bg-gray-100 animate-pulse" /> }
);

function DashboardContent() {
  const [selectedProperty, setSelectedProperty] = useState<PropertySummary | null>(null);
  const bounds = useMapStore((s) => s.bounds);

  const [suburb] = useQueryState("suburb", parseAsString.withDefault(""));
  const [type] = useQueryState("property_type", parseAsString.withDefault(""));
  const [bedsMin] = useQueryState("bedrooms_min", parseAsInteger.withDefault(0));
  const [undervalMin] = useQueryState("underval_score_min", parseAsFloat.withDefault(0));

  const filters = {
    suburb: suburb || undefined,
    property_type: type || undefined,
    bedrooms_min: bedsMin || undefined,
    underval_score_min: undervalMin || undefined,
    bbox: bounds ? boundsTobbox(bounds) : undefined,
    status: "for_sale",
    limit: 100,
  };

  const { data, isLoading } = useProperties(filters);
  const properties = data?.items ?? [];

  return (
    <PageShell title="Dashboard" fullHeight>
      <div className="flex flex-col h-full overflow-hidden">
        <div className="px-6 pt-6 bg-[#F8F9FB]">
          <KpiCards />
        </div>

        <FilterBar />

        <div className="flex flex-1 overflow-hidden">
          <div className="w-[440px] flex-shrink-0 flex flex-col border-r border-gray-200 bg-white overflow-hidden">
            <div className="px-4 py-2 border-b border-gray-100">
              <p className="text-xs text-gray-500">
                {isLoading ? "Loading…" : `${data?.total ?? 0} properties`}
                {bounds ? " in view" : ""}
              </p>
            </div>
            <PropertyList
              properties={properties}
              isLoading={isLoading}
              onPropertyClick={setSelectedProperty}
            />
          </div>

          <div className="flex-1 relative">
            <PropertyMap properties={properties} onPropertyClick={setSelectedProperty} />
          </div>
        </div>
      </div>

      <PropertyDetailDrawer property={selectedProperty} onClose={() => setSelectedProperty(null)} />
    </PageShell>
  );
}

export default function DashboardPage() {
  return (
    <Suspense>
      <DashboardContent />
    </Suspense>
  );
}
