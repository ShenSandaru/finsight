"use client";

import React from "react";
import { cn } from "@/lib/utils";
import {
  formatFinancialValue,
  formatMetricName,
  formatPeriod,
  parseTrendFinding,
  ParsedTrend,
} from "@/lib/utils/financial-formatter";
import { FinancialFinding } from "@/types/api";
import { useUiStore } from "@/stores/ui-store";
import { CagrTrendBadge } from "./cagr-trend-badge";
import { Button } from "@/components/ui/button";
import { FileText, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

interface MetricCardProps {
  finding: FinancialFinding;
  growthFinding?: FinancialFinding | null;
  cagrFinding?: FinancialFinding | null;
  trendFinding?: FinancialFinding | null;
  className?: string;
}

/**
 * Reusable Metric Card displaying key financial metrics with period tag,
 * formatted value, YoY growth indicator, trend badge, and citation evidence trigger.
 */
export function MetricCard({
  finding,
  growthFinding,
  cagrFinding,
  trendFinding,
  className,
}: MetricCardProps) {
  const openCitationDrawer = useUiStore((state) => state.openCitationDrawer);

  const parsedTrend: ParsedTrend | null = trendFinding
    ? parseTrendFinding(trendFinding)
    : null;

  const handleEvidenceClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (finding.source_chunk_ids && finding.source_chunk_ids.length > 0) {
      openCitationDrawer(finding.source_chunk_ids[0]);
    }
  };

  const hasEvidence = Boolean(finding.source_chunk_ids && finding.source_chunk_ids.length > 0);

  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-3.5 shadow-2xs hover:border-primary/30 transition-all flex flex-col justify-between space-y-2.5",
        className
      )}
      data-testid={`metric-card-${finding.metric}`}
    >
      {/* Top Header: Metric Name & Period Badge */}
      <div className="flex items-start justify-between gap-2">
        <span
          className="text-xs font-medium text-muted-foreground truncate"
          title={finding.calculation || finding.metric}
        >
          {formatMetricName(finding.metric)}
        </span>

        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-semibold uppercase tracking-wider shrink-0">
          {formatPeriod(finding.period)}
        </span>
      </div>

      {/* Main Metric Figure */}
      <div className="flex items-baseline justify-between gap-2">
        <span
          className="text-lg sm:text-xl font-bold font-mono tracking-tight text-foreground font-tabular-nums"
          data-testid="metric-value"
        >
          {formatFinancialValue(finding.value, finding.unit)}
        </span>

        {/* YoY Growth indicator if provided */}
        {growthFinding && (
          <div
            className={cn(
              "flex items-center gap-0.5 text-xs font-mono font-semibold",
              growthFinding.value > 0
                ? "text-finance-positive"
                : growthFinding.value < 0
                ? "text-finance-negative"
                : "text-muted-foreground"
            )}
            title={`YoY Change: ${formatPeriod(growthFinding.period)}`}
            data-testid="metric-yoy-growth"
          >
            {growthFinding.value > 0 ? (
              <ArrowUpRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            ) : growthFinding.value < 0 ? (
              <ArrowDownRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            ) : (
              <Minus className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            )}
            <span>
              {growthFinding.value > 0
                ? `+${growthFinding.value.toFixed(1)}%`
                : `${growthFinding.value.toFixed(1)}%`}
            </span>
          </div>
        )}
      </div>

      {/* Footer: Trend / CAGR badge & Evidence Link */}
      <div className="flex items-center justify-between gap-2 pt-1 border-t text-[11px]">
        <div>
          {parsedTrend ? (
            <CagrTrendBadge
              trend={parsedTrend}
              cagrValue={cagrFinding ? cagrFinding.value : null}
            />
          ) : cagrFinding ? (
            <CagrTrendBadge
              cagrValue={cagrFinding.value}
              periodRange={formatPeriod(cagrFinding.period)}
            />
          ) : (
            <span className="text-[10px] text-muted-foreground/80 font-mono">
              Audited figure
            </span>
          )}
        </div>

        {hasEvidence && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleEvidenceClick}
            className="h-5 px-1.5 py-0 text-[10px] font-mono text-primary/80 hover:text-primary gap-1 shrink-0"
            title="Inspect source evidence chunk"
            data-testid="metric-evidence-button"
          >
            <FileText className="h-3 w-3 shrink-0" />
            <span>Evidence</span>
          </Button>
        )}
      </div>
    </div>
  );
}
