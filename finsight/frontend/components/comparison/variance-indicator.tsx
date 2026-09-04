"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface VarianceIndicatorProps {
  value: number;
  unit?: string;
  className?: string;
  showGlyph?: boolean;
  neutralThreshold?: number;
}

/**
 * Presentation-only component displaying backend-provided variance information.
 * Uses direction glyph + formatted value.
 * DOES NOT calculate variances or judge financial health.
 */
export function VarianceIndicator({
  value,
  unit = "%",
  className,
  showGlyph = true,
  neutralThreshold = 0.001,
}: VarianceIndicatorProps) {
  if (value === null || value === undefined || isNaN(value)) {
    return <span className="text-muted-foreground font-mono text-xs">—</span>;
  }

  const isFlat = Math.abs(value) <= neutralThreshold;
  const isPositive = !isFlat && value > 0;
  const isNegative = !isFlat && value < 0;

  const glyph = isFlat ? "→" : isPositive ? "↑" : "↓";
  const sign = isPositive ? "+" : "";

  // Pure presentation formatting of backend value
  let formattedText = "";
  if (unit === "%") {
    formattedText = `${sign}${value.toFixed(2)}%`;
  } else if (unit === "$" || unit.toLowerCase() === "usd") {
    const abs = Math.abs(value);
    if (abs >= 1_000_000_000) {
      formattedText = `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
    } else if (abs >= 1_000_000) {
      formattedText = `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
    } else if (abs >= 1_000) {
      formattedText = `${sign}$${(abs / 1_000).toFixed(2)}K`;
    } else {
      formattedText = `${sign}$${abs.toFixed(2)}`;
    }
    if (isNegative) {
      formattedText = `(${formattedText.replace("+", "")})`;
    }
  } else {
    formattedText = `${sign}${value.toFixed(2)} ${unit}`.trim();
  }

  const directionLabel = isFlat
    ? "Flat / No Change"
    : isPositive
    ? "Positive Variance"
    : "Negative Variance";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-mono font-medium text-xs tabular-nums",
        isPositive && "text-emerald-500 dark:text-emerald-400",
        isNegative && "text-rose-500 dark:text-rose-400",
        isFlat && "text-muted-foreground",
        className
      )}
      aria-label={`${directionLabel}: ${formattedText}`}
      data-testid="variance-indicator"
    >
      {showGlyph && (
        <span className="font-sans text-[13px] font-bold select-none" aria-hidden="true">
          {glyph}
        </span>
      )}
      <span>{formattedText}</span>
    </span>
  );
}
