import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

export interface KPICardProps {
  title: string;
  value: string;
  trend?: string; // e.g., "+14.2%" or "-0.4%"
  trendDirection?: "up" | "down" | "neutral";
  context?: string; // e.g., "Compared to last quarter"
}

export default function KPICard({ title, value, trend, trendDirection = "neutral", context }: KPICardProps) {
  // Determine color matching for trend indicators
  const isUp = trendDirection === "up" || (trend && trend.startsWith("+"));
  const isDown = trendDirection === "down" || (trend && trend.startsWith("-"));

  let trendColor = "text-app-text-secondary bg-gray-100";
  let TrendIcon = Minus;

  if (isUp) {
    trendColor = "text-app-success bg-green-50";
    TrendIcon = ArrowUpRight;
  } else if (isDown) {
    trendColor = "text-app-error bg-red-50";
    TrendIcon = ArrowDownRight;
  }

  return (
    <div className="bg-app-surface border border-app-border rounded-lg p-4 flex flex-col justify-between shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
      <div className="flex justify-between items-start">
        <span className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider">
          {title}
        </span>
        {trend && (
          <span className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-xs font-semibold ${trendColor}`}>
            <TrendIcon size={12} />
            {trend}
          </span>
        )}
      </div>
      <div className="mt-2.5">
        <div className="text-2xl font-bold tracking-tight text-app-text-primary">
          {value}
        </div>
        {context && (
          <div className="text-xs text-app-text-secondary mt-1">
            {context}
          </div>
        )}
      </div>
    </div>
  );
}
