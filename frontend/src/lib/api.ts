const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  return res.json() as Promise<T>;
}

// --- Types ---

export interface ValuationSummary {
  predicted_value: number | null;
  underval_score_pct: number | null;
  model_version: string | null;
}

export interface PropertySummary {
  id: number;
  source: string;
  url: string;
  status: string;
  property_type: string | null;
  address: string | null;
  address_suburb: string | null;
  address_postcode: string | null;
  latitude: number | null;
  longitude: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  car_spaces: number | null;
  land_size_sqm: number | null;
  list_price: number | null;
  listed_at: string | null;
  valuation: ValuationSummary | null;
}

export interface PropertyListResponse {
  items: PropertySummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface SuburbStats {
  median_price: number | null;
  rental_yield_pct: number | null;
  capital_growth_1yr: number | null;
  capital_growth_3yr: number | null;
  capital_growth_5yr: number | null;
  snapshot_date: string | null;
}

export interface Suburb {
  id: number;
  name: string;
  postcode: string;
  lga: string | null;
  latitude: number | null;
  longitude: number | null;
  stats: SuburbStats;
}

// --- Property queries ---

export interface PropertyFilters {
  suburb?: string;
  postcode?: string;
  property_type?: string;
  bedrooms_min?: number;
  bedrooms_max?: number;
  price_min?: number;
  price_max?: number;
  land_size_min?: number;
  underval_score_min?: number;
  status?: string;
  bbox?: string;
  sort_by?: string;
  sort_dir?: string;
  limit?: number;
  offset?: number;
}

function buildQuery(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") {
      params.set(k, String(v));
    }
  }
  const q = params.toString();
  return q ? `?${q}` : "";
}

export const api = {
  properties: {
    list: (filters: PropertyFilters) =>
      apiFetch<PropertyListResponse>(`/properties${buildQuery(filters)}`),
    undervalued: (limit = 30, property_type?: string) =>
      apiFetch<PropertyListResponse>(
        `/properties/undervalued${buildQuery({ limit, property_type })}`
      ),
    get: (id: number) => apiFetch<PropertySummary>(`/properties/${id}`),
    valuation: (id: number) => apiFetch<object>(`/properties/${id}/valuation`),
  },
  suburbs: {
    list: (params?: object) => apiFetch<Suburb[]>(`/suburbs${buildQuery(params ?? {})}`),
    get: (id: number) => apiFetch<Suburb>(`/suburbs/${id}`),
    stats: (id: number) => apiFetch<object[]>(`/suburbs/${id}/stats`),
    map: () => apiFetch<object>(`/suburbs/map`),
    properties: (id: number, limit = 20) =>
      apiFetch<PropertyListResponse>(`/suburbs/${id}/properties${buildQuery({ limit })}`),
  },
  watchlist: {
    get: (sessionId: string) =>
      apiFetch<object[]>(`/watchlist`, { headers: { "X-Session-ID": sessionId } }),
    add: (sessionId: string, propertyId: number, notes?: string) =>
      apiFetch<object>(`/watchlist`, {
        method: "POST",
        headers: { "X-Session-ID": sessionId },
        body: JSON.stringify({ property_id: propertyId, notes }),
      }),
    remove: (sessionId: string, propertyId: number) =>
      apiFetch<void>(`/watchlist/${propertyId}`, {
        method: "DELETE",
        headers: { "X-Session-ID": sessionId },
      }),
    updateNotes: (sessionId: string, propertyId: number, notes: string) =>
      apiFetch<object>(`/watchlist/${propertyId}`, {
        method: "PATCH",
        headers: { "X-Session-ID": sessionId },
        body: JSON.stringify({ notes }),
      }),
  },
  valuations: {
    modelInfo: () => apiFetch<object>(`/valuations/model-info`),
  },
};
