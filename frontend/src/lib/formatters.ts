export function formatPrice(cents: number | null | undefined): string {
  if (cents == null) return "Price on request";
  const dollars = cents;
  if (dollars >= 1_000_000) return `$${(dollars / 1_000_000).toFixed(2)}M`;
  if (dollars >= 1_000) return `$${(dollars / 1_000).toFixed(0)}k`;
  return `$${dollars.toLocaleString("en-AU")}`;
}

export function formatScore(score: number | null | undefined): string {
  if (score == null) return "—";
  const sign = score > 0 ? "+" : "";
  return `${sign}${score.toFixed(1)}%`;
}

export function formatArea(sqm: number | null | undefined): string {
  if (sqm == null) return "—";
  return `${sqm.toLocaleString("en-AU")} m²`;
}

export function formatRelativeDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}yr ago`;
}
