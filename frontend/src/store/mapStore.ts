"use client";

import { create } from "zustand";

interface MapBounds {
  south: number;
  west: number;
  north: number;
  east: number;
}

interface MapStore {
  bounds: MapBounds | null;
  zoom: number;
  setBounds: (bounds: MapBounds) => void;
  setZoom: (zoom: number) => void;
  hoveredPropertyId: number | null;
  setHoveredPropertyId: (id: number | null) => void;
}

export const useMapStore = create<MapStore>((set) => ({
  bounds: null,
  zoom: 11,
  setBounds: (bounds) => set({ bounds }),
  setZoom: (zoom) => set({ zoom }),
  hoveredPropertyId: null,
  setHoveredPropertyId: (id) => set({ hoveredPropertyId: id }),
}));

export function boundsTobbox(bounds: MapBounds): string {
  return `${bounds.south},${bounds.west},${bounds.north},${bounds.east}`;
}
