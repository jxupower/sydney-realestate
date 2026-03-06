export interface SuburbStats {
  median_price: number | null;
  median_price_house: number | null;
  median_price_unit: number | null;
  rental_yield_pct: number | null;
  capital_growth_1yr: number | null;
  capital_growth_3yr: number | null;
  capital_growth_5yr: number | null;
  capital_growth_10yr: number | null;
  days_on_market_median: number | null;
  clearance_rate_pct: number | null;
  snapshot_date: string | null;
}

export interface Suburb {
  id: number;
  name: string;
  postcode: string;
  lga: string | null;
  state: string;
  latitude: number | null;
  longitude: number | null;
  boundary_geojson?: string;
  stats: Partial<SuburbStats>;
}
