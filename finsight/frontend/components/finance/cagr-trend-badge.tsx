"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { ParsedTrend, TrendDirection } from "@/lib/utils/financial-formatter";
import { TrendingUp, TrendingDown, Minus, Activity } from "lucide-react";

interface CagrTrendBadgeProps {
  trend?: ParsedTrend | null;
  cagrValue?: number | null;
  periodRange?: string | null;
  metricName?: string | null;
  className?: string;
}

/**
 * Dual-channel badge indicating Trend Direction and/or multi-period CAGR.
 * Accessible with text labels and geometric glyphs in addition to semantic coloring.
 */
export function CagrTrendBadge({
  trend,
  cagrValue,
  periodRange,
  metricName,
  className,
}: CagrTrendBadgeProps) {
  if (!trend && cagrValue === null && cagrValue === undefined) {
    return null;
  }

  const direction: TrendDirection = trend?.direction || (cagrValue && cagrValue > 0 ? "improving" : cagrValue && cagrValue < 0 ? "declining" : "neutral");

  const getVariantStyles = (dir: TrendDirection) => {
    switch (dir) {
      case "improving":
        return {
          container: "border-finance-positive/30 bg-finance-positive/10 text-finance-positive",
          icon: <TrendingUp className="h-3 w-3 shrink-0" aria-hidden="true" />,
          glyph: "↑",
        };
      case "declining":
        return {
          container: "border-finance-negative/30 bg-finance-negative/10 text-finance-negative",
          icon: <TrendingDown className="h-3 w-3 shrink-0" aria-hidden="true" />,
          glyph: "↓",
        };
      case "volatile":
        return {
          container: "border-finance-warning/30 bg-finance-warning/10 text-finance-warning",
          icon: <Activity className="h-3 w-3 shrink-0" aria-hidden="true" />,
          glyph: "~",
        };
      case "flat":
      case "neutral":
      default:
        return {
          container: "border-finance-neutral/30 bg-finance-neutral/10 text-finance-neutral",
          icon: <Minus className="h-3 w-3 shrink-0" aria-hidden="true" />,
          glyph: "→",
        };
    }
  };

  const styles = getVariantStyles(direction);

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-[11px] font-mono font-medium transition-colors select-none",
        styles.container,
        className
      )}
      data-testid="cagr-trend-badge"
      data-direction={direction}
      title={trend?.sequence ? `Sequence: ${trend.sequence}` : undefined}
    >
      <span aria-hidden="true" className="font-bold">
        {styles.glyph}
      </span>
      {styles.icon}

      <div className="flex items-center gap-1">
        {cagrValue !== null && cagrValue !== undefined && (
          <span className="font-semibold font-tabular-nums">
            {cagrValue > 0 ? `+${cagrValue.toFixed(1)}%` : `${cagrValue.toFixed(1)}%`} CAGR
          </span>
        )}

        {trend && (
          <span className="capitalize">
            {trend.label}
          </span>
        )}

        {periodRange && (
          <span className="text-[10px] opacity-75 font-normal">
            ({periodRange})
          </span>
        )}
      </div>
    </div>
  );
}
