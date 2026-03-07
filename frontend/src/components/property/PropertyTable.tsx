"use client";

import { ArrowUp, ArrowDown, ExternalLink, Bookmark, BookmarkCheck } from "lucide-react";
import { useQueryState, parseAsString } from "nuqs";
import { UndervalBadge } from "@/components/ui/UndervalBadge";
import { formatPrice, formatArea, formatRelativeDate } from "@/lib/formatters";
import { useWatchlist, useWatchlistMutations } from "@/hooks/useWatchlist";
import type { PropertySummary } from "@/lib/api";

interface PropertyTableProps {
  properties: PropertySummary[];
  total: number;
  limit: number;
  offset: number;
  onPropertyClick: (p: PropertySummary) => void;
  onOffsetChange: (offset: number) => void;
}

const COLS = [
  { key: "listed_at", label: "Listed" },
  { key: "price", label: "Price" },
  { key: "underval_score", label: "Underval %" },
  { key: "bedrooms", label: "Beds" },
];

function SortHeader({ col, label }: { col: string; label: string }) {
  const [sortBy, setSortBy] = useQueryState("sort_by", parseAsString.withDefault("listed_at"));
  const [sortDir, setSortDir] = useQueryState("sort_dir", parseAsString.withDefault("desc"));

  const active = sortBy === col;

  function toggle() {
    if (active) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  }

  return (
    <th
      onClick={toggle}
      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide cursor-pointer hover:text-gray-800 select-none whitespace-nowrap"
    >
      <span className="flex items-center gap-1">
        {label}
        {active ? (
          sortDir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />
        ) : (
          <span className="opacity-0 group-hover:opacity-50">
            <ArrowDown size={12} />
          </span>
        )}
      </span>
    </th>
  );
}

export function PropertyTable({
  properties,
  total,
  limit,
  offset,
  onPropertyClick,
  onOffsetChange,
}: PropertyTableProps) {
  const { data: watchlist } = useWatchlist();
  const { add, remove } = useWatchlistMutations();

  const watchlistIds = new Set(
    (watchlist as Array<{ property_id: number }> | undefined)?.map((w) => w.property_id) ?? []
  );

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 sticky top-0 z-10 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide w-72">
                Property
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                Type
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                Beds
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                Land
              </th>
              {COLS.map((c) => (
                <SortHeader key={c.key} col={c.key} label={c.label} />
              ))}
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                Predicted
              </th>
              <th className="w-16" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {properties.map((p) => {
              const isWatched = watchlistIds.has(p.id);
              return (
                <tr
                  key={p.id}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => onPropertyClick(p)}
                >
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium text-gray-900 truncate max-w-[260px]">
                        {p.address ?? `${p.address_suburb}, ${p.address_postcode}`}
                      </p>
                      <p className="text-xs text-gray-400">{p.address_suburb}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="capitalize text-gray-600 text-xs bg-gray-100 px-2 py-0.5 rounded">
                      {p.property_type ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{p.bedrooms ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                    {formatArea(p.land_size_sqm)}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                    {formatRelativeDate(p.listed_at)}
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">
                    {formatPrice(p.list_price)}
                  </td>
                  <td className="px-4 py-3">
                    <UndervalBadge score={p.valuation?.underval_score_pct} size="sm" />
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-600 whitespace-nowrap">
                    {p.valuation?.predicted_value != null
                      ? formatPrice(p.valuation.predicted_value)
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() =>
                          isWatched
                            ? remove.mutate(p.id)
                            : add.mutate({ propertyId: p.id })
                        }
                        className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-indigo-600 transition-colors"
                        title={isWatched ? "Remove from watchlist" : "Add to watchlist"}
                      >
                        {isWatched ? <BookmarkCheck size={14} /> : <Bookmark size={14} />}
                      </button>
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-indigo-600 transition-colors"
                        title="Open listing"
                      >
                        <ExternalLink size={14} />
                      </a>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {properties.length === 0 && (
          <div className="text-center py-12 text-sm text-gray-400">No properties match your filters.</div>
        )}
      </div>

      {/* Pagination */}
      <div className="border-t border-gray-200 px-4 py-3 flex items-center justify-between text-sm text-gray-500">
        <span>
          Showing {offset + 1}–{Math.min(offset + limit, total)} of {total.toLocaleString()}
        </span>
        <div className="flex items-center gap-1">
          <button
            disabled={currentPage <= 1}
            onClick={() => onOffsetChange(offset - limit)}
            className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40 hover:border-indigo-400 hover:text-indigo-600 transition-colors"
          >
            Prev
          </button>
          <span className="px-2">
            {currentPage} / {totalPages}
          </span>
          <button
            disabled={currentPage >= totalPages}
            onClick={() => onOffsetChange(offset + limit)}
            className="px-3 py-1 rounded border border-gray-200 disabled:opacity-40 hover:border-indigo-400 hover:text-indigo-600 transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
