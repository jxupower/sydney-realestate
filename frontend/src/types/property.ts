export interface ValuationSummary {
  predicted_value: number | null;
  underval_score_pct: number | null;
  confidence_interval?: [number | null, number | null];
  feature_importances?: Record<string, number>;
  model_version: string | null;
  predicted_at?: string;
}

export interface PropertySummary {
  id: number;
  source: string;
  url: string;
  status: "for_sale" | "sold" | "withdrawn";
  property_type: "house" | "apartment" | "townhouse" | "land" | "rural" | null;
  address: string | null;
  address_suburb: string | null;
  address_postcode: string | null;
  suburb_id: number | null;
  latitude: number | null;
  longitude: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  car_spaces: number | null;
  land_size_sqm: number | null;
  floor_area_sqm: number | null;
  list_price: number | null;
  listed_at: string | null;
  valuation: ValuationSummary | null;
}

export interface PropertyDetail extends PropertySummary {
  address_street: string | null;
  year_built: number | null;
  price_guide_low: number | null;
  price_guide_high: number | null;
  sold_price: number | null;
  sold_at: string | null;
  description: string | null;
  features: string[] | null;
  images: string[];
  agent_name: string | null;
  agency_name: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface PropertyFilters {
  suburb?: string;
  postcode?: string;
  property_type?: string;
  bedrooms_min?: number;
  price_min?: number;
  price_max?: number;
  land_size_min?: number;
  underval_score_min?: number;
  bbox?: string;
  sort_by?: string;
  limit?: number;
  offset?: number;
}
