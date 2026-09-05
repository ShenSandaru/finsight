"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { FinancialFinding } from "@/types/api";
import { MetricCard } from "./metric-card";
import { RatioTable } from "./ratio-table";
import { CagrTrendBadge } from "./cagr-trend-badge";
import {
  categorizeFinding,
  formatPeriod,
  formatMetricName,
  parseTrendFinding,
} from "@/lib/utils/financial-formatter";
import { TrendingUp, Layers, BarChart3 } from "lucide-react";

interface FindingListProps {
  findings?: FinancialFinding[];
  className?: string;
}

/**
 * Main structured financial findings presentation container.
 * Groups findings into Key Metrics, Financial Ratios & Margins, and Growth/Trends.
 * Displays only backend-provided figures with full evidence traceability.
 */
export function FindingList({ findings = [], className }: FindingListProps) {
  if (!findings || findings.length === 0) {
    return null;
  }

  // 1. Group findings by categorized presentation bucket
  const baseMetrics: FinancialFinding[] = [];
  const ratios: FinancialFinding[] = [];
  const growthList: FinancialFinding[] = [];
  const cagrList: FinancialFinding[] = [];
  const trendList: FinancialFinding[] = [];

  for (const f of findings) {
    const category = categorizeFinding(f);
    switch (category) {
      case "metric":
        baseMetrics.push(f);
        break;
      case "ratio":
        ratios.push(f);
        break;
      case "growth":
        growthList.push(f);
        break;
      case "cagr":
        cagrList.push(f);
        break;
      case "trend":
        trendList.push(f);
        break;
    }
  }

  // Quick lookups for associated growth/cagr/trend to decorate metric cards
  const growthMap: Record<string, FinancialFinding> = {};
  for (const gf of growthList) {
    const base = gf.metric.replace(/_growth$/, "");
    growthMap[base] = gf;
  }

  const cagrMap: Record<string, FinancialFinding> = {};
  for (const cf of cagrList) {
    const base = cf.metric.replace(/_cagr$/, "");
    cagrMap[base] = cf;
  }

  const trendMap: Record<string, FinancialFinding> = {};
  for (const tf of trendList) {
    const base = tf.metric.replace(/_trend$/, "");
    trendMap[base] = tf;
  }

  const hasMetrics = baseMetrics.length > 0;
  const hasRatios = ratios.length > 0;
  const hasGrowthOrCagr = growthList.length > 0 || cagrList.length > 0;

  return (
    <div
      className={cn("space-y-4 pt-3 mt-3 border-t border-border/60", className)}
      data-testid="financial-findings-container"
    >
      {/* Section Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-primary/10 text-primary">
            <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" />
          </div>
          <h3 className="text-xs font-semibold text-foreground tracking-wide uppercase">
            Audited Financial Findings
          </h3>
        </div>
        <span className="text-[10px] font-mono text-muted-foreground">
          {findings.length} findings • backend validated
        </span>
      </div>

      {/* 1. Key Metrics Grid */}
      {hasMetrics && (
        <div className="space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {baseMetrics.map((finding, idx) => (
              <MetricCard
                key={`metric-${finding.metric}-${finding.period}-${finding.document_id || idx}`}
                finding={finding}
                growthFinding={growthMap[finding.metric]}
                cagrFinding={cagrMap[finding.metric]}
                trendFinding={trendMap[finding.metric]}
              />
            ))}
          </div>
        </div>
      )}

      {/* 2. Financial Ratios & Margins Table */}
      {hasRatios && (
        <RatioTable ratioFindings={ratios} trendFindings={trendList} />
      )}

      {/* 3. Multi-Period Growth & CAGR Badges (for items not tied to a single card) */}
      {hasGrowthOrCagr && (
        <div
          className="rounded-lg border bg-muted/20 p-3 space-y-2"
          data-testid="growth-summary-container"
        >
          <div className="flex items-center gap-1.5 text-muted-foreground text-xs">
            <TrendingUp className="h-3.5 w-3.5 text-primary" />
            <span className="font-semibold text-foreground text-[11px] uppercase tracking-wider">
              Growth Dynamics & CAGR
            </span>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            {cagrList.map((cf) => {
              const baseName = cf.metric.replace(/_cagr$/, "");
              return (
                <CagrTrendBadge
                  key={`cagr-${cf.metric}-${cf.period}`}
                  cagrValue={cf.value}
                  periodRange={formatPeriod(cf.period)}
                  metricName={formatMetricName(baseName)}
                />
              );
            })}

            {trendList.map((tf) => {
              const baseName = tf.metric.replace(/_trend$/, "");
              const parsed = parseTrendFinding(tf);
              return (
                <div
                  key={`trend-${tf.metric}-${tf.period}`}
                  className="inline-flex items-center gap-1"
                >
                  <span className="text-[11px] text-muted-foreground font-medium">
                    {formatMetricName(baseName)}:
                  </span>
                  <CagrTrendBadge
                    trend={parsed}
                    periodRange={formatPeriod(tf.period)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
