"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import {
  ConversationQueryResponse,
  FinancialFinding,
  DocumentResponse,
  CitationResponse,
} from "@/types/api";
import { ComparisonTable } from "./comparison-table";
import { CitationPill } from "@/components/research/citation-pill";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  GitCompare,
  Download,
  Copy,
  Check,
  FileBarChart2,
  HelpCircle,
  ExternalLink,
  Layers,
} from "lucide-react";
import Link from "next/link";

interface ComparisonViewProps {
  response: ConversationQueryResponse;
  documents?: DocumentResponse[];
  className?: string;
  onGenerateReport?: () => void;
}

/**
 * Full Comparison View Container displaying:
 * 1. Scope summary of compared documents
 * 2. Institutional ComparisonTable with backend-provided variances
 * 3. Narrative Analyst Answer with [SOURCE N] CitationPills
 * 4. Export / Copy options
 */
export function ComparisonView({
  response,
  documents = [],
  className,
  onGenerateReport,
}: ComparisonViewProps) {
  const [copied, setCopied] = useState(false);

  const findings = response.findings || [];
  const citations = response.citations || [];

  // Categorize comparison findings vs standard findings
  const comparisonFindings = findings.filter(
    (f) =>
      f.metric.endsWith("_comparison") ||
      f.metric.endsWith("_absolute_difference") ||
      f.document_id !== null
  );

  const handleCopy = async () => {
    try {
      const summaryText = `Cross-Document Comparison\n\nQuery: ${response.query}\n\n${response.answer}`;
      await navigator.clipboard.writeText(summaryText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard fallback
    }
  };

  const handleDownload = () => {
    const summaryText = `# Cross-Document Financial Comparison\n\n**Query:** ${response.query}\n\n## Analyst Summary\n${response.answer}\n\n## Comparison Findings\n${JSON.stringify(
      findings,
      null,
      2
    )}`;
    const blob = new Blob([summaryText], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `comparison-${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  /**
   * Render assistant narrative answer, converting [SOURCE N] citations
   * into interactive CitationPills.
   */
  const renderNarrativeWithCitations = (text: string) => {
    if (!text) return null;
    const parts = text.split(/(\[SOURCE \d+\])/g);

    return parts.map((part, pIdx) => {
      const match = part.match(/\[SOURCE (\d+)\]/);
      if (match) {
        const sourceNum = match[1];
        const num = parseInt(sourceNum, 10);
        const cit = citations[num - 1];

        return (
          <CitationPill
            key={`cite-${pIdx}-${sourceNum}`}
            sourceNumber={sourceNum}
            chunkId={cit?.chunk_id}
            similarity={cit?.similarity}
            statementType={cit?.statement_type}
            fiscalPeriods={cit?.fiscal_periods}
          />
        );
      }
      return <span key={`text-${pIdx}`}>{part}</span>;
    });
  };

  return (
    <div
      className={cn("space-y-6 animate-in fade-in-50 duration-200", className)}
      data-testid="comparison-view"
    >
      {/* View Header & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-xl border bg-card shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <GitCompare className="h-4 w-4" />
            </div>
            <h2 className="text-base font-semibold text-foreground">
              Cross-Document Comparison Results
            </h2>
            <Badge variant="outline" className="text-xs font-mono">
              {findings.length} findings
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Grounded comparative financial analysis across selected filings with verified metric isolation.
          </p>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            className="h-8 px-2.5 text-xs gap-1.5"
            data-testid="copy-comparison-btn"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                <span>Copy Summary</span>
              </>
            )}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDownload}
            className="h-8 px-2.5 text-xs gap-1.5"
            data-testid="download-comparison-btn"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Export Markdown</span>
          </Button>

          {onGenerateReport && (
            <Button
              size="sm"
              onClick={onGenerateReport}
              className="h-8 px-3 text-xs gap-1.5"
              data-testid="comparison-generate-report-btn"
            >
              <FileBarChart2 className="h-3.5 w-3.5" />
              <span>Generate Report</span>
            </Button>
          )}
        </div>
      </div>

      {/* 1. Structured Side-by-Side Comparison Table */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
            1. Audited Metric & Variance Comparison
          </h3>
          <span className="text-[11px] text-muted-foreground font-mono">
            Directly from backend Financial Analyzer
          </span>
        </div>
        <ComparisonTable findings={comparisonFindings} documents={documents} />
      </div>

      {/* 2. Narrative Comparative Research Answer */}
      <div
        className="rounded-xl border bg-card p-5 space-y-3 shadow-xs"
        data-testid="comparison-narrative-section"
      >
        <div className="flex items-center justify-between border-b pb-2.5">
          <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
            2. Synthesis & Comparative Analyst Takeaways
          </h3>
          {citations.length > 0 && (
            <span className="text-[11px] text-muted-foreground font-mono">
              {citations.length} grounded citation{citations.length > 1 ? "s" : ""}
            </span>
          )}
        </div>

        <div className="prose prose-sm dark:prose-invert max-w-none text-xs leading-relaxed text-foreground whitespace-pre-wrap font-sans">
          {renderNarrativeWithCitations(response.answer)}
        </div>
      </div>
    </div>
  );
}
