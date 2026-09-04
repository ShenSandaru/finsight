"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { FinancialFinding, DocumentResponse } from "@/types/api";
import {
  formatFinancialValue,
  formatMetricName,
  formatPeriod,
} from "@/lib/utils/financial-formatter";
import { VarianceIndicator } from "./variance-indicator";
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
import { Badge } from "@/components/ui/badge";
import { FileText, ExternalLink, HelpCircle } from "lucide-react";

interface ComparisonTableProps {
  findings: FinancialFinding[];
  documents?: DocumentResponse[];
  className?: string;
}

interface ComparableRow {
  baseMetric: string;
  period: string;
  displayPeriod: string;
  docValues: Record<string, FinancialFinding>;
  absoluteDifference?: FinancialFinding;
  percentageComparison?: FinancialFinding;
  sourceChunkIds: string[];
}

/**
 * Institutional cross-document financial comparison table.
 * Strictly presents backend-computed figures without frontend calculations.
 * - Base metric values come from document-scoped findings.
 * - Absolute difference comes from backend {metric}_absolute_difference finding.
 * - Percentage difference comes from backend {metric}_comparison finding.
 * - Evidence opens Phase 11.5 CitationDrawer.
 */
export function ComparisonTable({
  findings = [],
  documents = [],
  className,
}: ComparisonTableProps) {
  const openCitationDrawer = useUiStore((state) => state.openCitationDrawer);

  // Group findings into comparable rows
  const rows: ComparableRow[] = React.useMemo(() => {
    if (!findings || findings.length === 0) return [];

    // Map documents to quick lookup
    const rowMap: Record<string, ComparableRow> = {};

    // First pass: identify absolute difference and percentage comparison findings
    for (const f of findings) {
      if (f.metric.endsWith("_absolute_difference")) {
        const base = f.metric.replace(/_absolute_difference$/, "");
        // e.g. period: '2025_docB_vs_docA' -> base period '2025'
        const basePeriod = f.period.replace(/_docB_vs_docA$/, "");
        const key = `${base}__${basePeriod}`;

        if (!rowMap[key]) {
          rowMap[key] = {
            baseMetric: base,
            period: basePeriod,
            displayPeriod: formatPeriod(basePeriod),
            docValues: {},
            sourceChunkIds: [...(f.source_chunk_ids || [])],
          };
        }
        rowMap[key].absoluteDifference = f;
        if (f.source_chunk_ids) {
          rowMap[key].sourceChunkIds = Array.from(
            new Set([...rowMap[key].sourceChunkIds, ...f.source_chunk_ids])
          );
        }
      } else if (f.metric.endsWith("_comparison")) {
        const base = f.metric.replace(/_comparison$/, "");
        const basePeriod = f.period.replace(/_docB_vs_docA$/, "");
        const key = `${base}__${basePeriod}`;

        if (!rowMap[key]) {
          rowMap[key] = {
            baseMetric: base,
            period: basePeriod,
            displayPeriod: formatPeriod(basePeriod),
            docValues: {},
            sourceChunkIds: [...(f.source_chunk_ids || [])],
          };
        }
        rowMap[key].percentageComparison = f;
        if (f.source_chunk_ids) {
          rowMap[key].sourceChunkIds = Array.from(
            new Set([...rowMap[key].sourceChunkIds, ...f.source_chunk_ids])
          );
        }
      }
    }

    // Second pass: associate base findings that have a document_id
    for (const f of findings) {
      if (
        f.document_id &&
        !f.metric.endsWith("_comparison") &&
        !f.metric.endsWith("_absolute_difference") &&
        !f.metric.endsWith("_growth") &&
        !f.metric.endsWith("_cagr") &&
        !f.metric.endsWith("_trend")
      ) {
        const key = `${f.metric}__${f.period}`;
        if (rowMap[key]) {
          rowMap[key].docValues[f.document_id] = f;
          if (f.source_chunk_ids) {
            rowMap[key].sourceChunkIds = Array.from(
              new Set([...rowMap[key].sourceChunkIds, ...f.source_chunk_ids])
            );
          }
        }
      }
    }

    return Object.values(rowMap);
  }, [findings]);

  // Determine list of documents present in the comparison
  const comparedDocs = React.useMemo(() => {
    const docIdsInFindings = new Set<string>();
    for (const f of findings) {
      if (f.document_id) {
        docIdsInFindings.add(f.document_id);
      }
    }

    // Filter documents from props or create clean fallback objects
    const list: Array<{ id: string; label: string; subLabel: string }> = [];
    const ids = Array.from(docIdsInFindings).sort();

    ids.forEach((id, idx) => {
      const matched = documents.find((d) => d.id === id);
      const letter = String.fromCharCode(65 + idx);
      list.push({
        id,
        label: matched?.title || matched?.filename || `Filing ${letter}`,
        subLabel: `Doc ${letter} (${id.slice(0, 8)})`,
      });
    });

    return list;
  }, [findings, documents]);

  if (rows.length === 0) {
    return (
      <div
        className="p-8 text-center rounded-xl border border-dashed text-muted-foreground bg-muted/10 space-y-2"
        data-testid="no-comparison-findings"
      >
        <HelpCircle className="h-6 w-6 mx-auto text-muted-foreground/60" />
        <p className="text-xs font-medium text-foreground">
          No comparable financial findings were returned for these filings.
        </p>
        <p className="text-[11px] text-muted-foreground max-w-md mx-auto">
          The backend Financial Analyzer extracts matching (metric, period) pairs across filings.
          Ensure both filings contain corresponding financial statements for the same fiscal period.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn("rounded-xl border bg-card shadow-xs overflow-hidden", className)}
      data-testid="comparison-table-container"
    >
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40 border-b">
              {/* Sticky Metric column */}
              <TableHead className="min-w-[180px] py-3 px-4 font-semibold text-foreground sticky left-0 bg-muted/40 z-10">
                Financial Metric
              </TableHead>
              <TableHead className="w-[100px] py-3 px-3 font-semibold text-foreground font-mono text-center">
                Period
              </TableHead>

              {/* Per-Document Columns */}
              {comparedDocs.map((doc) => (
                <TableHead
                  key={doc.id}
                  className="min-w-[140px] py-3 px-3 text-right font-semibold text-foreground"
                >
                  <div className="flex flex-col items-end">
                    <span className="truncate max-w-[150px]" title={doc.label}>
                      {doc.label}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground font-normal">
                      {doc.subLabel}
                    </span>
                  </div>
                </TableHead>
              ))}

              {/* Backend Authoritative Variance Columns */}
              <TableHead className="min-w-[130px] py-3 px-3 text-right font-semibold text-foreground">
                <div className="flex flex-col items-end">
                  <span>Variance</span>
                  <span className="text-[10px] text-muted-foreground font-normal">
                    (Doc B - Doc A)
                  </span>
                </div>
              </TableHead>

              <TableHead className="min-w-[130px] py-3 px-3 text-right font-semibold text-foreground">
                <div className="flex flex-col items-end">
                  <span>Variance (%)</span>
                  <span className="text-[10px] text-muted-foreground font-normal">
                    Direction
                  </span>
                </div>
              </TableHead>

              <TableHead className="w-[80px] py-3 px-3 text-center font-semibold text-foreground">
                Evidence
              </TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {rows.map((row) => {
              const absDiff = row.absoluteDifference;
              const pctComp = row.percentageComparison;
              const primaryChunkId = row.sourceChunkIds[0];

              return (
                <TableRow
                  key={`${row.baseMetric}-${row.period}`}
                  className="hover:bg-muted/30 transition-colors border-b last:border-b-0"
                  data-testid={`comparison-row-${row.baseMetric}`}
                >
                  {/* Metric Name */}
                  <TableCell className="py-2.5 px-4 font-medium text-foreground sticky left-0 bg-card z-10 border-r sm:border-r-0">
                    <div className="flex flex-col">
                      <span className="text-xs">{formatMetricName(row.baseMetric)}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {row.baseMetric}
                      </span>
                    </div>
                  </TableCell>

                  {/* Period */}
                  <TableCell className="py-2.5 px-3 text-center font-mono text-xs text-muted-foreground font-medium">
                    {row.displayPeriod}
                  </TableCell>

                  {/* Document Values */}
                  {comparedDocs.map((doc) => {
                    const finding = row.docValues[doc.id];
                    return (
                      <TableCell
                        key={doc.id}
                        className="py-2.5 px-3 text-right font-mono text-xs text-foreground tabular-nums"
                        data-testid={`cell-${row.baseMetric}-${doc.id}`}
                      >
                        {finding ? (
                          formatFinancialValue(finding.value, finding.unit)
                        ) : (
                          <span className="text-muted-foreground/50">—</span>
                        )}
                      </TableCell>
                    );
                  })}

                  {/* Backend Absolute Difference */}
                  <TableCell
                    className="py-2.5 px-3 text-right font-mono text-xs tabular-nums"
                    data-testid={`abs-diff-${row.baseMetric}`}
                  >
                    {absDiff ? (
                      <span className={cn(
                        "font-medium",
                        absDiff.value > 0 ? "text-foreground" : absDiff.value < 0 ? "text-muted-foreground" : "text-muted-foreground"
                      )}>
                        {formatFinancialValue(absDiff.value, absDiff.unit)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>

                  {/* Backend Percentage Comparison & Direction */}
                  <TableCell
                    className="py-2.5 px-3 text-right tabular-nums"
                    data-testid={`pct-diff-${row.baseMetric}`}
                  >
                    {pctComp ? (
                      <VarianceIndicator value={pctComp.value} unit={pctComp.unit} />
                    ) : (
                      <span className="text-muted-foreground font-mono text-xs">—</span>
                    )}
                  </TableCell>

                  {/* Evidence Drawer Trigger */}
                  <TableCell className="py-2.5 px-3 text-center">
                    {primaryChunkId ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openCitationDrawer(primaryChunkId)}
                        className="h-7 px-2 text-xs gap-1 text-primary hover:text-primary hover:bg-primary/10"
                        title={`View evidence chunk ${primaryChunkId.slice(0, 8)}`}
                        aria-label={`View evidence for ${formatMetricName(row.baseMetric)}`}
                        data-testid={`evidence-btn-${row.baseMetric}`}
                      >
                        <FileText className="h-3.5 w-3.5" />
                        <span className="font-mono text-[10px]">
                          {row.sourceChunkIds.length > 1
                            ? `${row.sourceChunkIds.length}`
                            : "Src"}
                        </span>
                      </Button>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Footer Provenance Note */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-muted/20 border-t text-[11px] text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <span className="font-semibold text-foreground">Backend Provenance:</span>
          <span>
            Variances & percentages are deterministically computed by FinSight Financial Analyzer Node.
          </span>
        </div>
        <span className="font-mono text-[10px]">
          {rows.length} comparable metrics • {comparedDocs.length} filings
        </span>
      </div>
    </div>
  );
}
