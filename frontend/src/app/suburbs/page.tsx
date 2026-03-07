"use client";

import { Suspense, useState } from "react";
import { useQueryState, parseAsString } from "nuqs";
import Link from "next/link";
import { ArrowUp, ArrowDown } from "lucide-react";
import { PageShell } from "@/components/layout/PageShell";
import { useSuburbs } from "@/hooks/useSuburbs";
import { formatPrice } from "@/lib/formatters";
import type { Suburb, SuburbListResponse } from "@/lib/api";

function SortTh({
  col,
  label,
  sortBy,
  sortDir,
  onSort,
}: {
  col: string;
  label: string;
  sortBy: string;
  sortDir: string;
  onSort: (col: string) => void;
}) {
  const active = sortBy === col;
  return (
    <th
      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide cursor-pointer hover:text-gray-800 select-none whitespace-nowrap"
      onClick={() => onSort(col)}
    >
      <span className="flex items-center gap-1">
        {label}
        {active ? sortDir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} /> : null}
      </span>
    </th>
  );
}

function SuburbsContent() {
  const [sortBy, setSortBy] = useState("median_price");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [lga] = useQueryState("lga", parseAsString.withDefault(""));
  const [postcode] = useQueryState("postcode", parseAsString.withDefault(""));

  const { data: suburbs, isLoading } = useSuburbs({
    lga: lga || undefined,
    postcode: postcode || undefined,
    sort_by: sortBy,
  });

  function handleSort(col: string) {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  }

  const raw = suburbs as SuburbListResponse | Suburb[] | undefined;
  const items: Suburb[] = Array.isArray(raw) ? raw : raw?.items ?? [];

  const sorted = [...items].sort((a, b) => {
    const av = (a.stats?.[sortBy as keyof typeof a.stats] ?? 0) as number;
    const bv = (b.stats?.[sortBy as keyof typeof b.stats] ?? 0) as number;
    return sortDir === "asc" ? av - bv : bv - av;
  });

  return (
    <PageShell title="Suburbs">
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <p className="text-sm text-gray-500">
            {isLoading ? "Loading…" : `${sorted.length} suburbs tracked`}
          </p>
        </div>

        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Suburb
                </th>
                <SortTh col="median_price" label="Median Price" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
                <SortTh col="capital_growth_1yr" label="1yr Growth" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
                <SortTh col="capital_growth_3yr" label="3yr Growth" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
                <SortTh col="rental_yield_pct" label="Rental Yield" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  LGA
                </th>
                <th className="w-16" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sorted.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{s.name}</p>
                    <p className="text-xs text-gray-400">{s.postcode}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {s.stats?.median_price ? formatPrice(s.stats.median_price) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {s.stats?.capital_growth_1yr != null ? (
                      <span className={s.stats.capital_growth_1yr >= 0 ? "text-emerald-600" : "text-red-500"}>
                        {s.stats.capital_growth_1yr >= 0 ? "+" : ""}
                        {s.stats.capital_growth_1yr.toFixed(1)}%
                      </span>
                    ) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {s.stats?.capital_growth_3yr != null ? (
                      <span className={s.stats.capital_growth_3yr >= 0 ? "text-emerald-600" : "text-red-500"}>
                        {s.stats.capital_growth_3yr >= 0 ? "+" : ""}
                        {s.stats.capital_growth_3yr.toFixed(1)}%
                      </span>
                    ) : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {s.stats?.rental_yield_pct != null ? `${s.stats.rental_yield_pct.toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{s.lga ?? "—"}</td>
                  <td className="px-4 py-3">
                    <Link href={`/suburbs/${s.id}`} className="text-xs text-indigo-600 hover:underline">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {!isLoading && sorted.length === 0 && (
            <div className="text-center py-12 text-sm text-gray-400">No suburb data available.</div>
          )}
        </div>
      </div>
    </PageShell>
  );
}

export default function SuburbsPage() {
  return (
    <Suspense>
      <SuburbsContent />
    </Suspense>
  );
}
