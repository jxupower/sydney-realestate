"use client";

import { PropertyRow } from "./PropertyRow";
import type { PropertySummary } from "@/lib/api";

interface PropertyListProps {
  properties: PropertySummary[];
  isLoading?: boolean;
  onPropertyClick: (property: PropertySummary) => void;
}

export function PropertyList({ properties, isLoading, onPropertyClick }: PropertyListProps) {
  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-gray-400">
        Loading properties…
      </div>
    );
  }

  if (properties.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-sm text-gray-400 gap-2 py-12">
        <p>No properties found.</p>
        <p className="text-xs">Try adjusting your filters.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {properties.map((p) => (
        <PropertyRow key={p.id} property={p} onClick={onPropertyClick} />
      ))}
    </div>
  );
}
