"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type PropertyFilters } from "@/lib/api";

export function useProperties(filters: PropertyFilters) {
  return useQuery({
    queryKey: ["properties", filters],
    queryFn: () => api.properties.list(filters),
  });
}

export function useProperty(id: number) {
  return useQuery({
    queryKey: ["property", id],
    queryFn: () => api.properties.get(id),
    enabled: id > 0,
  });
}

export function usePropertyValuation(id: number) {
  return useQuery({
    queryKey: ["property-valuation", id],
    queryFn: () => api.properties.valuation(id),
    enabled: id > 0,
  });
}

export function useUndervaluedProperties(limit = 30) {
  return useQuery({
    queryKey: ["undervalued-properties", limit],
    queryFn: () => api.properties.undervalued(limit),
  });
}
