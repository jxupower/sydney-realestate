"use client";

import { Bed, Bath, Car, Maximize2 } from "lucide-react";
import { UndervalBadge } from "@/components/ui/UndervalBadge";
import { formatPrice, formatRelativeDate } from "@/lib/formatters";
import { useMapStore } from "@/store/mapStore";
import type { PropertySummary } from "@/lib/api";

interface PropertyRowProps {
  property: PropertySummary;
  onClick: (property: PropertySummary) => void;
}

export function PropertyRow({ property: p, onClick }: PropertyRowProps) {
  const setHovered = useMapStore((s) => s.setHoveredPropertyId);

  return (
    <div
      className="flex items-start gap-3 px-4 py-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors"
      onClick={() => onClick(p)}
      onMouseEnter={() => setHovered(p.id)}
      onMouseLeave={() => setHovered(null)}
    >
      {/* Thumbnail placeholder */}
      <div className="w-14 h-14 rounded-md bg-gray-100 flex-shrink-0 overflow-hidden">
        {/* No images in list view — placeholder */}
        <div className="w-full h-full bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center text-gray-300">
          <Maximize2 size={18} />
        </div>
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">
          {p.address ?? `${p.address_suburb}, ${p.address_postcode}`}
        </p>
        <p className="text-xs text-gray-400 mb-1.5">
          {p.address_suburb}
          {p.address_postcode ? ` · ${p.address_postcode}` : ""}
          {" · "}
          {p.property_type ?? "property"}
        </p>

        <div className="flex items-center gap-3 text-xs text-gray-500">
          {p.bedrooms != null && (
            <span className="flex items-center gap-0.5">
              <Bed size={11} /> {p.bedrooms}
            </span>
          )}
          {p.bathrooms != null && (
            <span className="flex items-center gap-0.5">
              <Bath size={11} /> {p.bathrooms}
            </span>
          )}
          {p.car_spaces != null && (
            <span className="flex items-center gap-0.5">
              <Car size={11} /> {p.car_spaces}
            </span>
          )}
          {p.land_size_sqm != null && (
            <span>{p.land_size_sqm.toLocaleString()} m²</span>
          )}
        </div>
      </div>

      <div className="flex-shrink-0 text-right space-y-1">
        <p className="text-sm font-semibold text-gray-900">{formatPrice(p.list_price)}</p>
        <UndervalBadge score={p.valuation?.underval_score_pct} size="sm" />
        <p className="text-xs text-gray-400">{formatRelativeDate(p.listed_at)}</p>
      </div>
    </div>
  );
}
