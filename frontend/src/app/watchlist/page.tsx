"use client";

import { useState } from "react";
import { Trash2, Edit3, Check } from "lucide-react";
import { PageShell } from "@/components/layout/PageShell";
import { PropertyDetailDrawer } from "@/components/property/PropertyDetailDrawer";
import { UndervalBadge } from "@/components/ui/UndervalBadge";
import { formatPrice, formatRelativeDate } from "@/lib/formatters";
import { useWatchlist, useWatchlistMutations } from "@/hooks/useWatchlist";
import type { PropertySummary, WatchlistItem } from "@/lib/api";

export default function WatchlistPage() {
  const { data, isLoading } = useWatchlist();
  const { remove, updateNotes } = useWatchlistMutations();
  const [selectedProperty, setSelectedProperty] = useState<PropertySummary | null>(null);
  const [editingNotes, setEditingNotes] = useState<number | null>(null);
  const [notesValue, setNotesValue] = useState("");

  const items = (data as WatchlistItem[] | undefined) ?? [];

  function startEditNotes(item: WatchlistItem) {
    setEditingNotes(item.id);
    setNotesValue(item.notes ?? "");
  }

  function saveNotes(item: WatchlistItem) {
    updateNotes.mutate({ propertyId: item.property_id, notes: notesValue });
    setEditingNotes(null);
  }

  return (
    <PageShell title="Watchlist">
      {isLoading ? (
        <div className="text-sm text-gray-400">Loading watchlist…</div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <p className="text-gray-500 text-sm">Your watchlist is empty.</p>
          <p className="text-xs text-gray-400 mt-1">
            Save properties from the dashboard or properties page.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100">
            <p className="text-sm text-gray-500">{items.length} saved properties</p>
          </div>
          <div className="divide-y divide-gray-100">
            {items.map((item) => {
              const p = item.property;
              return (
                <div
                  key={item.id}
                  className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors"
                >
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => p && setSelectedProperty(p)}
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="font-medium text-gray-900 truncate">
                        {p?.address ?? `Property #${item.property_id}`}
                      </p>
                      {p?.valuation?.underval_score_pct != null && (
                        <UndervalBadge score={p.valuation.underval_score_pct} size="sm" />
                      )}
                    </div>
                    <p className="text-xs text-gray-400">
                      {p?.address_suburb ?? ""}
                      {p?.listed_at ? ` · Listed ${formatRelativeDate(p.listed_at)}` : ""}
                      {p?.list_price ? ` · ${formatPrice(p.list_price)}` : ""}
                    </p>
                  </div>

                  <div className="w-48 text-sm">
                    {editingNotes === item.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          autoFocus
                          value={notesValue}
                          onChange={(e) => setNotesValue(e.target.value)}
                          className="flex-1 text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-indigo-400"
                          onKeyDown={(e) => e.key === "Enter" && saveNotes(item)}
                          onBlur={() => saveNotes(item)}
                        />
                        <button
                          onClick={() => saveNotes(item)}
                          className="p-1 text-indigo-600 hover:text-indigo-800"
                        >
                          <Check size={14} />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => startEditNotes(item)}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700 transition-colors group"
                      >
                        <span className="truncate">{item.notes || "Add notes…"}</span>
                        <Edit3
                          size={11}
                          className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        />
                      </button>
                    )}
                  </div>

                  <button
                    onClick={() => remove.mutate(item.property_id)}
                    className="p-2 text-gray-300 hover:text-red-500 transition-colors rounded-md hover:bg-red-50"
                    title="Remove from watchlist"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <PropertyDetailDrawer
        property={selectedProperty}
        onClose={() => setSelectedProperty(null)}
      />
    </PageShell>
  );
}
