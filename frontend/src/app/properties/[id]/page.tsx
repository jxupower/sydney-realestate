"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bed, Bath, Car, ExternalLink, MapPin } from "lucide-react";
import Link from "next/link";
import { PageShell } from "@/components/layout/PageShell";
import { ValuationBreakdown } from "@/components/property/ValuationBreakdown";
import { UndervalBadge } from "@/components/ui/UndervalBadge";
import { formatPrice, formatArea, formatRelativeDate } from "@/lib/formatters";
import { api, type ValuationDetail } from "@/lib/api";

export default function PropertyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const propertyId = Number(id);

  const { data: property, isLoading } = useQuery({
    queryKey: ["property", propertyId],
    queryFn: () => api.properties.get(propertyId),
  });

  const { data: valuation } = useQuery({
    queryKey: ["property-valuation", propertyId],
    queryFn: () => api.properties.valuation(propertyId),
    enabled: !!property,
  });

  if (isLoading) {
    return (
      <PageShell title="Property Detail">
        <div className="flex items-center justify-center h-40 text-sm text-gray-400">Loading…</div>
      </PageShell>
    );
  }

  if (!property) {
    return (
      <PageShell title="Property Not Found">
        <p className="text-sm text-gray-500">This property does not exist.</p>
      </PageShell>
    );
  }

  const detailRows: Array<[string, string | number | null | undefined]> = [
    ["Property type", property.property_type],
    ["Status", property.status],
    ["Year built", property.year_built],
    ["Floor area", property.floor_area_sqm ? formatArea(property.floor_area_sqm) : null],
    ["Land size", property.land_size_sqm ? formatArea(property.land_size_sqm) : null],
    ["Agent", property.agent_name],
    ["Agency", property.agency_name],
  ];

  return (
    <PageShell title={property.address ?? "Property Detail"}>
      <div className="max-w-4xl mx-auto">
        <Link
          href="/properties"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-indigo-600 mb-4 transition-colors"
        >
          <ArrowLeft size={14} />
          Back to Properties
        </Link>

        {/* Hero */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-6">
          <div className="h-56 bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center text-gray-300">
            <span className="text-sm">No photos available</span>
          </div>
          <div className="p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-xl font-semibold text-gray-900">
                  {property.address_street ?? property.address ?? "Address unavailable"}
                </h1>
                <p className="text-gray-500 flex items-center gap-1 mt-0.5">
                  <MapPin size={13} />
                  {property.address_suburb}
                  {property.address_postcode ? `, NSW ${property.address_postcode}` : ""}
                </p>
              </div>
              <UndervalBadge score={property.valuation?.underval_score_pct} />
            </div>

            <div className="flex items-center gap-5 mt-4 text-sm text-gray-600">
              {property.bedrooms != null && (
                <span className="flex items-center gap-1.5">
                  <Bed size={15} className="text-gray-400" /> {property.bedrooms} bed
                </span>
              )}
              {property.bathrooms != null && (
                <span className="flex items-center gap-1.5">
                  <Bath size={15} className="text-gray-400" /> {property.bathrooms} bath
                </span>
              )}
              {property.car_spaces != null && (
                <span className="flex items-center gap-1.5">
                  <Car size={15} className="text-gray-400" /> {property.car_spaces} car
                </span>
              )}
              {property.land_size_sqm != null && (
                <span>{formatArea(property.land_size_sqm)} land</span>
              )}
            </div>

            <div className="flex items-center gap-4 mt-4">
              <span className="text-2xl font-bold text-gray-900">
                {formatPrice(property.list_price)}
              </span>
              <span className="text-sm text-gray-400">
                Listed {formatRelativeDate(property.listed_at)}
              </span>
            </div>

            <div className="mt-4">
              <a
                href={property.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg border border-gray-200 hover:border-indigo-600 hover:text-indigo-600 transition-colors"
              >
                View on listing site <ExternalLink size={13} />
              </a>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Valuation */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Valuation Breakdown</h2>
            <ValuationBreakdown
              listPrice={property.list_price}
              valuation={valuation as ValuationDetail | null}
            />
          </div>

          {/* Details */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Details</h2>
            <div className="space-y-2 text-sm">
              {detailRows.map(([label, value]) =>
                value != null ? (
                  <div key={label} className="flex justify-between">
                    <span className="text-gray-500">{label}</span>
                    <span className="capitalize">{String(value)}</span>
                  </div>
                ) : null
              )}
            </div>

            {property.features && property.features.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
                  Features
                </p>
                <div className="flex flex-wrap gap-1">
                  {property.features.map((f, i) => (
                    <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </PageShell>
  );
}
