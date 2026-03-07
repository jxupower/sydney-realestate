"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useSessionId } from "./useSessionId";

export function useWatchlist() {
  const sessionId = useSessionId();
  return useQuery({
    queryKey: ["watchlist", sessionId],
    queryFn: () => api.watchlist.get(sessionId),
    enabled: !!sessionId,
  });
}

export function useWatchlistMutations() {
  const sessionId = useSessionId();
  const qc = useQueryClient();

  const invalidate = () => qc.invalidateQueries({ queryKey: ["watchlist", sessionId] });

  const add = useMutation({
    mutationFn: ({ propertyId, notes }: { propertyId: number; notes?: string }) =>
      api.watchlist.add(sessionId, propertyId, notes),
    onSuccess: invalidate,
  });

  const remove = useMutation({
    mutationFn: (propertyId: number) => api.watchlist.remove(sessionId, propertyId),
    onSuccess: invalidate,
  });

  const updateNotes = useMutation({
    mutationFn: ({ propertyId, notes }: { propertyId: number; notes: string }) =>
      api.watchlist.updateNotes(sessionId, propertyId, notes),
    onSuccess: invalidate,
  });

  return { add, remove, updateNotes };
}
