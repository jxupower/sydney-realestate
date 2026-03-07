"use client";

import { Search, SlidersHorizontal } from "lucide-react";
import { useQueryState, parseAsString, parseAsInteger, parseAsFloat } from "nuqs";

interface FilterBarProps {
  showUndervalFilter?: boolean;
}

export function FilterBar({ showUndervalFilter = true }: FilterBarProps) {
  const [suburb, setSuburb] = useQueryState("suburb", parseAsString.withDefault(""));
  const [type, setType] = useQueryState("property_type", parseAsString.withDefault(""));
  const [beds, setBeds] = useQueryState("bedrooms_min", parseAsInteger.withDefault(0));
  const [undervalMin, setUndervalMin] = useQueryState(
    "underval_score_min",
    parseAsFloat.withDefault(0)
  );

  return (
    <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100 bg-white flex-wrap">
      {/* Suburb search */}
      <div className="relative flex-1 min-w-[140px]">
        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Suburb…"
          value={suburb}
          onChange={(e) => setSuburb(e.target.value || null)}
          className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:border-indigo-400"
        />
      </div>

      {/* Type */}
      <select
        value={type}
        onChange={(e) => setType(e.target.value || null)}
        className="text-sm border border-gray-200 rounded-md px-2 py-1.5 text-gray-700 focus:outline-none focus:border-indigo-400"
      >
        <option value="">All types</option>
        <option value="house">House</option>
        <option value="apartment">Apartment</option>
        <option value="townhouse">Townhouse</option>
        <option value="land">Land</option>
      </select>

      {/* Beds */}
      <select
        value={beds ?? 0}
        onChange={(e) => setBeds(Number(e.target.value) || null)}
        className="text-sm border border-gray-200 rounded-md px-2 py-1.5 text-gray-700 focus:outline-none focus:border-indigo-400"
      >
        <option value={0}>Any beds</option>
        <option value={1}>1+ bed</option>
        <option value={2}>2+ beds</option>
        <option value={3}>3+ beds</option>
        <option value={4}>4+ beds</option>
      </select>

      {/* Underval filter */}
      {showUndervalFilter && (
        <select
          value={undervalMin ?? 0}
          onChange={(e) => setUndervalMin(Number(e.target.value) || null)}
          className="text-sm border border-gray-200 rounded-md px-2 py-1.5 text-gray-700 focus:outline-none focus:border-indigo-400"
        >
          <option value={0}>All properties</option>
          <option value={5}>5%+ undervalued</option>
          <option value={10}>10%+ undervalued</option>
          <option value={15}>15%+ undervalued</option>
          <option value={20}>20%+ undervalued</option>
        </select>
      )}
    </div>
  );
}
