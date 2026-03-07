"use client";

import { CircleMarker, Popup } from "react-leaflet";
import { scoreColor, scoreLabel } from "@/lib/constants";
import { formatPrice } from "@/lib/formatters";
import type { PropertySummary } from "@/lib/api";

interface PropertyMarkerProps {
  property: PropertySummary;
  isHovered?: boolean;
  onClick?: (property: PropertySummary) => void;
}

export function PropertyMarker({ property, isHovered, onClick }: PropertyMarkerProps) {
  const score = property.valuation?.underval_score_pct;
  const color = scoreColor(score);

  const radius = score != null && score > 10 ? 10 : score != null && score >= 0 ? 8 : 7;

  if (!property.latitude || !property.longitude) return null;

  return (
    <CircleMarker
      center={[property.latitude, property.longitude]}
      radius={isHovered ? radius + 4 : radius}
      pathOptions={{
        fillColor: color,
        fillOpacity: 0.85,
        color: isHovered ? "#fff" : color,
        weight: isHovered ? 2 : 1,
      }}
      eventHandlers={{
        click: () => onClick?.(property),
      }}
    >
      <Popup className="property-popup" maxWidth={220}>
        <div className="text-sm p-1">
          <p className="font-semibold text-gray-900 mb-0.5 leading-tight">
            {property.address_suburb ?? "Unknown suburb"}
          </p>
          <p className="text-gray-500 text-xs mb-1">{property.address}</p>
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">{formatPrice(property.list_price)}</span>
            <span
              className="text-xs font-semibold px-1.5 py-0.5 rounded"
              style={{ background: color + "22", color }}
            >
              {score != null ? `${score > 0 ? "+" : ""}${score.toFixed(1)}%` : scoreLabel(score)}
            </span>
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
}
