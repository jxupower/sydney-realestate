export const SYDNEY_CBD = { lat: -33.8688, lng: 151.2093 } as const;
export const SEARCH_RADIUS_KM = 150;

// Default map settings
export const MAP_DEFAULT_ZOOM = 11;
export const MAP_MIN_ZOOM = 8;
export const MAP_MAX_ZOOM = 18;

// Undervaluation score thresholds for colour coding
export const UNDERVAL_STRONG = 10;   // > 10% → green
export const UNDERVAL_FAIR = 0;      // 0–10% → yellow
// < 0% → red

export const SCORE_COLORS = {
  strong: "#10B981",   // green
  fair: "#F59E0B",     // yellow
  over: "#EF4444",     // red
  unknown: "#9CA3AF",  // grey
} as const;

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return SCORE_COLORS.unknown;
  if (score > UNDERVAL_STRONG) return SCORE_COLORS.strong;
  if (score >= UNDERVAL_FAIR) return SCORE_COLORS.fair;
  return SCORE_COLORS.over;
}

export function scoreLabel(score: number | null | undefined): string {
  if (score == null) return "No estimate";
  if (score > UNDERVAL_STRONG) return "Strong Buy";
  if (score >= UNDERVAL_FAIR) return "Fairly Priced";
  return "Overvalued";
}
