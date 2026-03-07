"use client";

import { useEffect } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import { SYDNEY_CBD, MAP_DEFAULT_ZOOM, MAP_MIN_ZOOM, MAP_MAX_ZOOM } from "@/lib/constants";
import { MapBoundsWatcher } from "@/hooks/useMapBounds";
import { PropertyMarker } from "./PropertyMarker";
import { useMapStore } from "@/store/mapStore";
import type { PropertySummary } from "@/lib/api";
import "leaflet/dist/leaflet.css";

// Fix Leaflet default icon in Next.js
import L from "leaflet";
// @ts-expect-error - leaflet internals
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

interface PropertyMapProps {
  properties: PropertySummary[];
  onPropertyClick?: (property: PropertySummary) => void;
}

function MapContent({ properties, onPropertyClick }: PropertyMapProps) {
  const hoveredId = useMapStore((s) => s.hoveredPropertyId);

  return (
    <>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <MapBoundsWatcher />
      {properties.map((p) => (
        <PropertyMarker
          key={p.id}
          property={p}
          isHovered={p.id === hoveredId}
          onClick={onPropertyClick}
        />
      ))}
    </>
  );
}

export function PropertyMap({ properties, onPropertyClick }: PropertyMapProps) {
  return (
    <MapContainer
      center={[SYDNEY_CBD.lat, SYDNEY_CBD.lng]}
      zoom={MAP_DEFAULT_ZOOM}
      minZoom={MAP_MIN_ZOOM}
      maxZoom={MAP_MAX_ZOOM}
      className="h-full w-full"
      style={{ background: "#e5e7eb" }}
    >
      <MapContent properties={properties} onPropertyClick={onPropertyClick} />
    </MapContainer>
  );
}
