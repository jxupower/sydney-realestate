"use client";

import { Suspense, useState } from "react";
import { useQueryState, parseAsString, parseAsInteger, parseAsFloat } from "nuqs";
import { PageShell } from "@/components/layout/PageShell";
import { FilterPanel } from "@/components/filters/FilterPanel";
import { PropertyTable } from "@/components/property/PropertyTable";
import { PropertyDetailDrawer } from "@/components/property/PropertyDetailDrawer";
import { useProperties } from "@/hooks/useProperties";
import type { PropertySummary } from "@/lib/api";

const PAGE_SIZE = 20;

function PropertiesContent() {
  const [selectedProperty, setSelectedProperty] = useState<PropertySummary | null>(null);
  const [offset, setOffset] = useState(0);

  const [suburb] = useQueryState("suburb", parseAsString.withDefault(""));
  const [type] = useQueryState("property_type", parseAsString.withDefault(""));
  const [bedsMin] = useQueryState("bedrooms_min", parseAsInteger.withDefault(0));
  const [priceMin] = useQueryState("price_min", parseAsFloat.withDefault(0));
  const [priceMax] = useQueryState("price_max", parseAsFloat.withDefault(0));
  const [undervalMin] = useQueryState("underval_score_min", parseAsFloat.withDefault(0));
  const [sortBy] = useQueryState("sort_by", parseAsString.withDefault("listed_at"));
  const [sortDir] = useQueryState("sort_dir", parseAsString.withDefault("desc"));

  const filters = {
    suburb: suburb || undefined,
    property_type: type || undefined,
    bedrooms_min: bedsMin || undefined,
    price_min: priceMin || undefined,
    price_max: priceMax || undefined,
    underval_score_min: undervalMin || undefined,
    sort_by: sortBy || undefined,
    sort_dir: sortDir || undefined,
    limit: PAGE_SIZE,
    offset,
  };

  const { data, isLoading } = useProperties(filters);

  return (
    <PageShell title="Properties" fullHeight>
      <div className="flex flex-col h-full overflow-hidden">
        <FilterPanel />

        <div className="flex-1 overflow-hidden bg-white">
          {isLoading ? (
            <div className="flex items-center justify-center h-full text-sm text-gray-400">
              Loading…
            </div>
          ) : (
            <PropertyTable
              properties={data?.items ?? []}
              total={data?.total ?? 0}
              limit={PAGE_SIZE}
              offset={offset}
              onPropertyClick={setSelectedProperty}
              onOffsetChange={setOffset}
            />
          )}
        </div>
      </div>

      <PropertyDetailDrawer
        property={selectedProperty}
        onClose={() => setSelectedProperty(null)}
      />
    </PageShell>
  );
}

export default function PropertiesPage() {
  return (
    <Suspense>
      <PropertiesContent />
    </Suspense>
  );
}
