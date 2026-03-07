"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSuburbs(params?: { lga?: string; postcode?: string; sort_by?: string }) {
  return useQuery({
    queryKey: ["suburbs", params],
    queryFn: () => api.suburbs.list(params as Record<string, unknown> | undefined),
  });
}

export function useSuburb(id: number) {
  return useQuery({
    queryKey: ["suburb", id],
    queryFn: () => api.suburbs.get(id),
    enabled: id > 0,
  });
}

export function useSuburbStats(id: number) {
  return useQuery({
    queryKey: ["suburb-stats", id],
    queryFn: () => api.suburbs.stats(id),
    enabled: id > 0,
  });
}

export function useSuburbMap() {
  return useQuery({
    queryKey: ["suburbs-map"],
    queryFn: () => api.suburbs.map(),
    staleTime: 5 * 60_000,
  });
}
