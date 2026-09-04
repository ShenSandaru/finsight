"use client";

import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { ComparisonSelector } from "@/components/comparison/comparison-selector";
import { ComparisonView } from "@/components/comparison/comparison-view";
import { CitationDrawer } from "@/components/citations/citation-drawer";
import { GenerateReportModal } from "@/components/reports/generate-report-modal";
import { useUiStore } from "@/stores/ui-store";
import { useDocuments } from "@/hooks/use-documents";
import { useCreateSession } from "@/hooks/use-conversations";
import { conversationsApi } from "@/lib/api/conversations";
import { ConversationQueryResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  GitCompare,
  ArrowRight,
  Loader2,
  AlertCircle,
  Sparkles,
  RefreshCw,
  HelpCircle,
} from "lucide-react";

const COMPARISON_PRESETS = [
  {
    label: "Comprehensive Financial Comparison",
    query:
      "Compare the selected filings across revenue, net income, operating margins, balance sheet strength, and key financial ratios.",
  },
  {
    label: "Revenue & Margin Variance",
    query:
      "Compare total revenue, gross margin, operating margin, and calculate material variances across these filings.",
  },
  {
    label: "Balance Sheet & Solvency Comparison",
    query:
      "Compare liquidity, total assets, current ratio, debt-to-equity, and cash flow across these filings.",
  },
];

export default function ComparePage() {
  const selectedDocumentIds = useUiStore((state) => state.selectedDocumentIds);
  const { data: documentsData } = useDocuments();
  const allDocs = documentsData?.documents || [];
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [queryInput, setQueryInput] = useState(
    "Compare the selected filings across revenue, gross margin, operating margin, and key financial variances."
  );
  const [comparisonResponse, setComparisonResponse] =
    useState<ConversationQueryResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);

  const { mutate: createSession, isPending: isCreatingSession } = useCreateSession();

  const [isQuerying, setIsQuerying] = useState(false);
  const meetsMinimum = selectedDocumentIds.length >= 2;

  const handleRunComparison = async (customQuery?: string) => {
    if (!meetsMinimum) return;

    const queryToExecute = (customQuery || queryInput).trim();
    if (!queryToExecute) return;

    setErrorMessage(null);
    setIsQuerying(true);

    try {
      const sessionId = activeSessionId || "44444444-4444-4444-4444-444444444444";
      if (!activeSessionId) {
        setActiveSessionId(sessionId);
      }

      const res = await conversationsApi.querySession(sessionId, {
        query: queryToExecute,
        document_ids: selectedDocumentIds,
      });

      setComparisonResponse(res);
    } catch (err: any) {
      setErrorMessage(err?.message || "Comparison query failed.");
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <AppShell>
      <div
        className="max-w-6xl mx-auto space-y-6 pb-16 px-4 sm:px-6"
        data-testid="compare-workspace-page"
      >
        {/* Workspace Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <GitCompare className="h-4 w-4" />
              </div>
              <h1 className="text-xl font-bold tracking-tight text-foreground">
                Cross-Document Comparison Workspace
              </h1>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Multi-filing side-by-side corporate analysis, deterministic variance calculations, and citation-backed evidence.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs font-mono">
              Phase 11.8 Active
            </Badge>
          </div>
        </div>

        {/* Step 1: Document Selection Scope */}
        <ComparisonSelector />

        {/* Step 2: Comparison Inquiry & Execution Bar */}
        <Card className="shadow-xs" data-testid="comparison-input-card">
          <CardContent className="p-4 sm:p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold text-foreground">
                  Comparison Inquiry
                </h2>
              </div>
              <span className="text-[11px] text-muted-foreground">
                Scopes LangGraph research across {selectedDocumentIds.length} filings
              </span>
            </div>

            {/* Presets */}
            <div className="flex flex-wrap gap-1.5" data-testid="comparison-presets">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider self-center mr-1">
                Presets:
              </span>
              {COMPARISON_PRESETS.map((preset) => (
                <Button
                  key={preset.label}
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setQueryInput(preset.query);
                    if (meetsMinimum) {
                      handleRunComparison(preset.query);
                    }
                  }}
                  className="h-7 text-[11px] px-2.5 rounded-full"
                  disabled={!meetsMinimum || isQuerying || isCreatingSession}
                >
                  {preset.label}
                </Button>
              ))}
            </div>

            {/* Query Input */}
            <div className="space-y-2">
              <Textarea
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="Enter comparative financial inquiry..."
                rows={2}
                disabled={isQuerying || isCreatingSession}
                className="text-xs resize-none min-h-[64px]"
                aria-label="Comparative financial inquiry input"
                data-testid="comparison-query-input"
              />

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <p className="text-[11px] text-muted-foreground">
                  Backend Financial Analyzer calculates isolated metrics, absolute variances, and percentage deltas.
                </p>

                <Button
                  onClick={() => handleRunComparison(queryInput)}
                  disabled={!meetsMinimum || !queryInput.trim() || isQuerying || isCreatingSession}
                  className="gap-2 h-8 px-4 text-xs font-semibold"
                  data-testid="execute-comparison-btn"
                >
                  {isQuerying || isCreatingSession ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Comparing Filings...</span>
                    </>
                  ) : (
                    <>
                      <span>Run Comparison</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Error State Banner */}
        {errorMessage && (
          <div
            className="flex items-center gap-2 p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs"
            role="alert"
            data-testid="comparison-error-banner"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Loading State Banner */}
        {(isQuerying || isCreatingSession) && (
          <Card
            className="border-primary/30 bg-primary/5 p-8 text-center space-y-3"
            data-testid="comparison-loading-state"
          >
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-foreground">
                Analyzing {selectedDocumentIds.length} Selected Filings...
              </h3>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                Extracting structured financial metrics, isolating company statements, computing verified variances, and mapping citation evidence.
              </p>
            </div>
          </Card>
        )}

        {/* Step 3: Comparison Results View */}
        {comparisonResponse && !isQuerying && (
          <ComparisonView
            response={comparisonResponse}
            documents={allDocs}
            onGenerateReport={() => setIsReportModalOpen(true)}
          />
        )}
      </div>

      {/* Generate Report Modal (Phase 11.7 integration) */}
      <GenerateReportModal
        open={isReportModalOpen}
        onOpenChange={setIsReportModalOpen}
        defaultTitle={`Cross-Document Comparison Report (${selectedDocumentIds.length} filings)`}
        defaultQuery={queryInput}
      />

      {/* Citation Drawer (Phase 11.5) */}
      <CitationDrawer />
    </AppShell>
  );
}
