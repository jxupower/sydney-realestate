"use client";

import { Search } from "lucide-react";
import { useQueryState, parseAsString, parseAsInteger, parseAsFloat } from "nuqs";

export function FilterPanel() {
  const [suburb, setSuburb] = useQueryState("suburb", parseAsString.withDefault(""));
  const [type, setType] = useQueryState("property_type", parseAsString.withDefault(""));
  const [bedsMin, setBedsMin] = useQueryState("bedrooms_min", parseAsInteger.withDefault(0));
  const [priceMin, setPriceMin] = useQueryState("price_min", parseAsFloat.withDefault(0));
  const [priceMax, setPriceMax] = useQueryState("price_max", parseAsFloat.withDefault(0));
  const [undervalMin, setUndervalMin] = useQueryState(
    "underval_score_min",
    parseAsFloat.withDefault(0)
  );
  const [sortBy, setSortBy] = useQueryState("sort_by", parseAsString.withDefault("listed_at"));
  const [sortDir, setSortDir] = useQueryState("sort_dir", parseAsString.withDefault("desc"));

  function clearAll() {
    setSuburb(null);
    setType(null);
    setBedsMin(null);
    setPriceMin(null);
    setPriceMax(null);
    setUndervalMin(null);
    setSortBy(null);
    setSortDir(null);
  }

  return (
    <div className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex flex-wrap gap-3 items-end">
        {/* Suburb */}
        <div className="flex flex-col gap-1 min-w-[180px]">
          <label className="text-xs font-medium text-gray-500">Suburb</label>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="e.g. Bondi"
              value={suburb}
              onChange={(e) => setSuburb(e.target.value || null)}
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:border-indigo-400"
            />
          </div>
        </div>

        {/* Type */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">Type</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value || null)}
            className="text-sm border border-gray-200 rounded-md px-2.5 py-1.5 text-gray-700 focus:outline-none focus:border-indigo-400"
          >
            <option value="">All</option>
            <option value="house">House</option>
            <option value="apartment">Apartment</option>
            <option value="townhouse">Townhouse</option>
            <option value="land">Land</option>
          </select>
        </div>

        {/* Bedrooms */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">Min beds</label>
          <select
            value={bedsMin ?? 0}
            onChange={(e) => setBedsMin(Number(e.target.value) || null)}
            className="text-sm border border-gray-200 rounded-md px-2.5 py-1.5 text-gray-700 focus:outline-none focus:border-indigo-400"
          >
            <option value={0}>Any</option>
            <option value={1}>1+</option>
            <option value={2}>2+</option>
            <option value={3}>3+</option>
            <option value={4}>4+</option>
          </select>
        </div>

        {/* Price range */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">Min price ($)</label>
          <input
            type="number"
            step={100000}
            placeholder="500,000"
            value={priceMin || ""}
            onChange={(e) => setPriceMin(Number(e.target.value) || null)}
            className="w-28 text-sm border border-gray-200 rounded-md px-2.5 py-1.5 focus:outline-none focus:border-indigo-400"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">Max price ($)</label>
          <input
            type="number"
            step={100000}
            placeholder="2,000,000"
            value={priceMax || ""}
            onChange={(e) => setPriceMax(Number(e.target.value) || null)}
            className="w-28 text-sm border border-gray-200 rounded-md px-2.5 py-1.5 focus:outline-none focus:border-indigo-400"
          />
        </div>

        {/* Underval min */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">Undervalued by</label>
          <select
            value={undervalMin ?? 0}
            onChange={(e) => setUndervalMin(Number(e.target.value) || null)}
            className="text-sm border border-gray-200 rounded-md px-2.5 py-1.5 text-gray-700 focus:outline-none focus:border-indigo-400"
          >
            <option value={0}>Any</option>
            <option value={5}>5%+</option>
            <option value={10}>10%+</option>
            <option value={15}>15%+</option>
            <option value={20}>20%+</option>
          </select>
        </div>

        {/* Sort */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">Sort by</label>
          <div className="flex gap-1">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value || null)}
              className="text-sm border border-gray-200 rounded-md px-2.5 py-1.5 text-gray-700 focus:outline-none focus:border-indigo-400"
            >
              <option value="listed_at">Listed</option>
              <option value="price">Price</option>
              <option value="underval_score">Underval %</option>
              <option value="bedrooms">Bedrooms</option>
            </select>
            <select
              value={sortDir}
              onChange={(e) => setSortDir(e.target.value || null)}
              className="text-sm border border-gray-200 rounded-md px-2.5 py-1.5 text-gray-700 focus:outline-none focus:border-indigo-400"
            >
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </select>
          </div>
        </div>

        <button
          onClick={clearAll}
          className="text-sm text-gray-500 hover:text-gray-800 underline self-end pb-1.5"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
