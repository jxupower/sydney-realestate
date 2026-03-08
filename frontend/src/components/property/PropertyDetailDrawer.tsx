"use client";

import { X, ExternalLink, Bookmark, BookmarkCheck, Bed, Bath, Car, Maximize2, MapPin } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { ValuationBreakdown } from "./ValuationBreakdown";
import { UndervalBadge } from "@/components/ui/UndervalBadge";
import { formatPrice, formatArea, formatRelativeDate } from "@/lib/formatters";
import { useWatchlist, useWatchlistMutations } from "@/hooks/useWatchlist";
import { api, type PropertySummary, type ValuationDetail, type WatchlistItem } from "@/lib/api";

interface PropertyDetailDrawerProps {
  property: PropertySummary | null;
  onClose: () => void;
}

export function PropertyDetailDrawer({ property, onClose }: PropertyDetailDrawerProps) {
  const { data: watchlist } = useWatchlist();
  const { add, remove } = useWatchlistMutations();

  const { data: detail } = useQuery({
    queryKey: ["property", property?.id],
    queryFn: () => api.properties.get(property!.id),
    enabled: property != null,
  });

  const { data: valuation } = useQuery({
    queryKey: ["property-valuation", property?.id],
    queryFn: () => api.properties.valuation(property!.id),
    enabled: property != null,
  });

  if (!property) return null;

  const watchlistIds = new Set(
    (watchlist as WatchlistItem[] | undefined)?.map((w) => w.property_id) ?? []
  );
  const isWatched = watchlistIds.has(property.id);

  const p = detail ?? property;

  const detailRows: Array<[string, string | number | null | undefined]> = [
    ["Type", p.property_type],
    ["Status", p.status],
    ["Year built", p.year_built],
    ["Floor area", p.floor_area_sqm ? formatArea(p.floor_area_sqm) : null],
    [
      "Price guide",
      p.price_guide_low && p.price_guide_high
        ? `${formatPrice(p.price_guide_low)} – ${formatPrice(p.price_guide_high)}`
        : p.price_guide_low
        ? `From ${formatPrice(p.price_guide_low)}`
        : null,
    ],
    ["Agent", p.agent_name ? `${p.agent_name}${p.agency_name ? ` · ${p.agency_name}` : ""}` : null],
    ["Listed", formatRelativeDate(p.listed_at)],
  ];

  return (
    <>
      {/* Backdrop — must be above Leaflet's max z-index (~1000) */}
      <div className="fixed inset-0 bg-black/10 z-[1001]" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[400px] bg-white shadow-2xl z-[1002] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-gray-100 text-gray-500 transition-colors"
          >
            <X size={18} />
          </button>

          <div className="flex items-center gap-2">
            <UndervalBadge score={p.valuation?.underval_score_pct} size="sm" />
            <button
              onClick={() =>
                isWatched
                  ? remove.mutate(property.id)
                  : add.mutate({ propertyId: property.id })
              }
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                isWatched
                  ? "bg-indigo-600 text-white hover:bg-indigo-700"
                  : "border border-gray-200 text-gray-700 hover:border-indigo-600 hover:text-indigo-600"
              }`}
            >
              {isWatched ? <BookmarkCheck size={14} /> : <Bookmark size={14} />}
              {isWatched ? "Saved" : "Save"}
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* Image placeholder */}
          <div className="h-48 bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center">
            <Maximize2 size={32} className="text-gray-300" />
          </div>

          <div className="px-5 py-4 space-y-5">
            {/* Address */}
            <div>
              <h2 className="text-lg font-semibold text-gray-900 leading-tight">
                {p.address_street ?? p.address ?? "Address unavailable"}
              </h2>
              <p className="text-sm text-gray-500 flex items-center gap-1 mt-0.5">
                <MapPin size={12} />
                {p.address_suburb}
                {p.address_postcode ? `, NSW ${p.address_postcode}` : ""}
              </p>
            </div>

            {/* Description */}
            {p.description && (
              <p className="text-sm text-gray-600 leading-relaxed">{p.description}</p>
            )}

            {/* Features */}
            {p.features && p.features.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {(p.features as string[]).map((f) => (
                  <span
                    key={f}
                    className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-xs capitalize"
                  >
                    {f}
                  </span>
                ))}
              </div>
            )}

            {/* Stats row */}
            <div className="flex items-center gap-4 text-sm text-gray-600 py-3 border-t border-b border-gray-100">
              {p.bedrooms != null && (
                <span className="flex items-center gap-1.5">
                  <Bed size={15} className="text-gray-400" />
                  {p.bedrooms} bed
                </span>
              )}
              {p.bathrooms != null && (
                <span className="flex items-center gap-1.5">
                  <Bath size={15} className="text-gray-400" />
                  {p.bathrooms} bath
                </span>
              )}
              {p.car_spaces != null && (
                <span className="flex items-center gap-1.5">
                  <Car size={15} className="text-gray-400" />
                  {p.car_spaces} car
                </span>
              )}
              {p.land_size_sqm != null && (
                <span className="text-gray-500">{formatArea(p.land_size_sqm)}</span>
              )}
            </div>

            {/* Valuation */}
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
                Valuation Breakdown
              </p>
              <ValuationBreakdown
                listPrice={p.list_price}
                valuation={valuation as ValuationDetail | null}
              />
            </div>

            {/* Property details */}
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Property Details
              </p>
              <div className="space-y-1.5 text-sm">
                {detailRows.map(([label, value]) =>
                  value != null ? (
                    <div key={label} className="flex justify-between">
                      <span className="text-gray-500">{label}</span>
                      <span className="capitalize">{String(value)}</span>
                    </div>
                  ) : null
                )}
              </div>
            </div>

            {/* External link */}
            <a
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg border border-gray-200 text-sm text-gray-700 hover:border-indigo-600 hover:text-indigo-600 transition-colors"
            >
              View on {p.source === "domain_api" ? "Domain" : "listing site"}
              <ExternalLink size={13} />
            </a>
          </div>
        </div>
      </div>
    </>
  );
}
