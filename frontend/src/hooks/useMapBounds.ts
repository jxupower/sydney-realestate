"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";
import { useMapStore } from "@/store/mapStore";

export function MapBoundsWatcher() {
  const map = useMap();
  const { setBounds, setZoom } = useMapStore();

  useEffect(() => {
    function updateBounds() {
      const b = map.getBounds();
      setBounds({
        south: b.getSouth(),
        west: b.getWest(),
        north: b.getNorth(),
        east: b.getEast(),
      });
      setZoom(map.getZoom());
    }

    updateBounds();
    map.on("moveend", updateBounds);
    return () => { map.off("moveend", updateBounds); };
  }, [map, setBounds, setZoom]);

  return null;
}
