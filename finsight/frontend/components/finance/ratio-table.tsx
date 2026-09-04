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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { FileText, TrendingUp, TrendingDown, Minus, Activity } from "lucide-react";

interface RatioTableProps {
  ratioFindings: FinancialFinding[];
  trendFindings?: FinancialFinding[];
  className?: string;
}

/**
 * Dense financial ratio comparison table across fiscal periods.
 * Completely driven by backend-derived metrics without frontend recalculation.
 */
export function RatioTable({
  ratioFindings,
  trendFindings = [],
  className,
}: RatioTableProps) {
  const openCitationDrawer = useUiStore((state) => state.openCitationDrawer);

  if (!ratioFindings || ratioFindings.length === 0) {
    return null;
  }

  // 1. Group findings by canonical metric and period
  // Structure: map of metric -> map of period -> FinancialFinding
  const metricMap: Record<string, Record<string, FinancialFinding>> = {};
  const periodsSet = new Set<string>();

  for (const f of ratioFindings) {
    if (!metricMap[f.metric]) {
      metricMap[f.metric] = {};
    }
    metricMap[f.metric][f.period] = f;
    periodsSet.add(f.period);
  }

  // Sort periods ascending or standard order (e.g. 2023, 2024, 2025)
  const sortedPeriods = Array.from(periodsSet).sort();

  // Create lookup for trends by base metric name
  const trendMap: Record<string, FinancialFinding> = {};
  for (const tf of trendFindings) {
    const base = tf.metric.replace(/_trend$/, "");
    trendMap[base] = tf;
  }

  const handleEvidenceClick = (chunkId: string) => {
    if (chunkId) {
      openCitationDrawer(chunkId);
    }
  };

  return (
    <div
      className={cn(
        "rounded-lg border bg-card overflow-hidden shadow-2xs",
        className
      )}
      data-testid="ratio-table-container"
    >
      <div className="px-4 py-2.5 bg-muted/40 border-b flex items-center justify-between">
        <div>
          <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
            Financial Ratios & Margins
          </h4>
          <p className="text-[11px] text-muted-foreground">
            Audited profitability, operational leverage, and liquidity ratios
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <Table className="w-full text-xs">
          <TableHeader className="bg-muted/20">
            <TableRow className="hover:bg-transparent">
              <TableHead className="py-2.5 px-4 font-semibold text-foreground">
                Metric / Ratio
              </TableHead>
              {sortedPeriods.map((period) => (
                <TableHead
                  key={`th-${period}`}
                  className="py-2.5 px-3 text-right font-semibold text-foreground font-mono"
                >
                  {formatPeriod(period)}
                </TableHead>
              ))}
              <TableHead className="py-2.5 px-3 text-center font-semibold text-foreground">
                Trend
              </TableHead>
              <TableHead className="py-2.5 px-3 text-right font-semibold text-foreground">
                Evidence
              </TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {Object.keys(metricMap).map((metricKey) => {
              const periodValues = metricMap[metricKey];
              const trendFinding = trendMap[metricKey];
              const parsedTrend: ParsedTrend | null = trendFinding
                ? parseTrendFinding(trendFinding)
                : null;

              // Extract first available source chunk ID for evidence button
              let sourceChunkId: string | null = null;
              for (const p of sortedPeriods) {
                if (periodValues[p]?.source_chunk_ids?.length) {
                  sourceChunkId = periodValues[p].source_chunk_ids[0];
                  break;
                }
              }

              return (
                <TableRow
                  key={`row-${metricKey}`}
                  className="hover:bg-muted/30 transition-colors border-b last:border-b-0"
                  data-testid={`ratio-row-${metricKey}`}
                >
                  {/* Metric Name */}
                  <TableCell className="py-2.5 px-4 font-medium text-foreground whitespace-nowrap">
                    {formatMetricName(metricKey)}
                  </TableCell>

                  {/* Period Figures */}
                  {sortedPeriods.map((period) => {
                    const finding = periodValues[period];
                    if (!finding) {
                      return (
                        <TableCell
                          key={`td-${metricKey}-${period}`}
                          className="py-2.5 px-3 text-right font-mono text-muted-foreground"
                        >
                          —
                        </TableCell>
                      );
                    }

                    const isNegative = finding.value < 0;

                    return (
                      <TableCell
                        key={`td-${metricKey}-${period}`}
                        className={cn(
                          "py-2.5 px-3 text-right font-mono font-medium font-tabular-nums whitespace-nowrap",
                          isNegative && "text-finance-negative"
                        )}
                      >
                        {formatFinancialValue(finding.value, finding.unit)}
                      </TableCell>
                    );
                  })}

                  {/* Trend Indicator */}
                  <TableCell className="py-2.5 px-3 text-center whitespace-nowrap">
                    {parsedTrend ? (
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 text-[11px] font-mono font-medium px-1.5 py-0.5 rounded",
                          parsedTrend.direction === "improving" &&
                            "text-finance-positive bg-finance-positive/10",
                          parsedTrend.direction === "declining" &&
                            "text-finance-negative bg-finance-negative/10",
                          parsedTrend.direction === "volatile" &&
                            "text-finance-warning bg-finance-warning/10",
                          (parsedTrend.direction === "flat" ||
                            parsedTrend.direction === "neutral") &&
                            "text-finance-neutral bg-finance-neutral/10"
                        )}
                        title={parsedTrend.label}
                      >
                        <span aria-hidden="true">{parsedTrend.glyph}</span>
                        <span>{parsedTrend.label.split(" ")[0]}</span>
                      </span>
                    ) : (
                      <span className="text-muted-foreground/60">—</span>
                    )}
                  </TableCell>

                  {/* Evidence Action */}
                  <TableCell className="py-2.5 px-3 text-right whitespace-nowrap">
                    {sourceChunkId ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEvidenceClick(sourceChunkId!)}
                        className="h-6 px-1.5 text-[10px] font-mono text-primary/80 hover:text-primary gap-1"
                        title="View underlying source chunk"
                        data-testid={`evidence-btn-${metricKey}`}
                      >
                        <FileText className="h-3 w-3" />
                        <span>Source</span>
                      </Button>
                    ) : (
                      <span className="text-muted-foreground/60 text-[10px]">—</span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
