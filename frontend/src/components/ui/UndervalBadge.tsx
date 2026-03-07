import { cn } from "./cn";
import { scoreColor, scoreLabel } from "@/lib/constants";
import { formatScore } from "@/lib/formatters";

interface UndervalBadgeProps {
  score: number | null | undefined;
  showLabel?: boolean;
  size?: "sm" | "md";
}

export function UndervalBadge({ score, showLabel = false, size = "md" }: UndervalBadgeProps) {
  const color = scoreColor(score);
  const label = scoreLabel(score);

  const colorClasses: Record<string, string> = {
    "#10B981": "bg-emerald-100 text-emerald-800",
    "#F59E0B": "bg-amber-100 text-amber-800",
    "#EF4444": "bg-red-100 text-red-800",
    "#9CA3AF": "bg-gray-100 text-gray-600",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        colorClasses[color] ?? "bg-gray-100 text-gray-600"
      )}
    >
      {score != null ? formatScore(score) : "—"}
      {showLabel && <span className="opacity-70">{label}</span>}
    </span>
  );
}
