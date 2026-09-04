"use client";

import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileBarChart2, Loader2, AlertCircle, Layers } from "lucide-react";
import { useCreateReport } from "@/hooks/use-reports";
import { useUiStore } from "@/stores/ui-store";
import { useRouter } from "next/navigation";

interface GenerateReportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultQuery?: string;
  defaultTitle?: string;
}

export function GenerateReportModal({
  open,
  onOpenChange,
  defaultQuery = "",
  defaultTitle = "",
}: GenerateReportModalProps) {
  const router = useRouter();
  const selectedDocumentIds = useUiStore((state) => state.selectedDocumentIds);
  const { mutate: createReport, isPending } = useCreateReport();

  const [query, setQuery] = useState(defaultQuery);
  const [title, setTitle] = useState(defaultTitle);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync state when modal opens with new defaults
  React.useEffect(() => {
    if (open) {
      setQuery(defaultQuery);
      setTitle(defaultTitle);
      setErrorMessage(null);
    }
  }, [open, defaultQuery, defaultTitle]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const trimmedQuery = query.trim();
    if (!trimmedQuery || trimmedQuery.length < 3) {
      setErrorMessage("Research query or theme must be at least 3 characters long.");
      return;
    }
    if (trimmedQuery.length > 1000) {
      setErrorMessage("Research query cannot exceed 1000 characters.");
      return;
    }

    createReport(
      {
        query: trimmedQuery,
        title: title.trim() ? title.trim() : undefined,
        document_ids: selectedDocumentIds.length > 0 ? selectedDocumentIds : undefined,
        report_type: "financial_research",
      },
      {
        onSuccess: (report) => {
          onOpenChange(false);
          router.push(`/reports/${report.id}`);
        },
        onError: (err) => {
          setErrorMessage(err.message || "Failed to submit financial research report request.");
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-lg bg-card text-card-foreground shadow-2xl border"
        data-testid="generate-report-modal"
      >
        <DialogHeader>
          <div className="flex items-center gap-2 text-primary mb-1">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-primary/10">
              <FileBarChart2 className="h-4 w-4" />
            </div>
            <DialogTitle className="text-base font-semibold">
              Generate Structured Research Report
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            Compile an institutional-grade financial research report with executive summary,
            verified metrics, CAGR trends, and source chunk provenance.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          {errorMessage && (
            <div
              className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive"
              role="alert"
              data-testid="generate-report-error"
            >
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Active Context: Selected Documents */}
          <div className="rounded-md border bg-muted/20 p-3 text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-primary" />
                Filing Scope
              </span>
              <Badge
                variant={selectedDocumentIds.length > 0 ? "financePositive" : "secondary"}
                className="text-[10px] px-1.5 py-0 h-4 font-tabular-nums"
                data-testid="generate-report-doc-count"
              >
                {selectedDocumentIds.length}{" "}
                {selectedDocumentIds.length === 1 ? "document" : "documents"} selected
              </Badge>
            </div>
            <p className="text-[11px] text-muted-foreground leading-snug">
              {selectedDocumentIds.length > 0
                ? "Vector retrieval and financial table analysis will be strictly scoped to your selected filings."
                : "No filings selected. Retrieval will query across the entire indexed filing repository."}
            </p>
          </div>

          {/* Report Title */}
          <div className="space-y-1.5">
            <label
              htmlFor="report-title"
              className="text-xs font-semibold text-foreground flex items-center justify-between"
            >
              <span>Report Title</span>
              <span className="text-[10px] text-muted-foreground font-normal">Optional</span>
            </label>
            <input
              id="report-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Apple Inc. FY2025 Comprehensive Ratio & Margin Analysis"
              maxLength={255}
              disabled={isPending}
              className="w-full rounded-md border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              data-testid="report-title-input"
            />
          </div>

          {/* Research Query / Topic */}
          <div className="space-y-1.5">
            <label
              htmlFor="report-query"
              className="text-xs font-semibold text-foreground flex items-center justify-between"
            >
              <span>Research Theme / Inquiry</span>
              <span className="text-[10px] text-muted-foreground font-normal">Required</span>
            </label>
            <textarea
              id="report-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Detail the research objectives, comparative metrics, or financial ratios to analyze..."
              rows={3}
              required
              minLength={3}
              maxLength={1000}
              disabled={isPending}
              className="w-full rounded-md border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring resize-none disabled:opacity-50"
              data-testid="report-query-input"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>Min 3 chars</span>
              <span>{query.length} / 1000</span>
            </div>
          </div>

          <DialogFooter className="pt-2 gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isPending || !query.trim()}
              className="text-xs gap-1.5"
              data-testid="submit-generate-report-btn"
            >
              {isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Enqueuing...</span>
                </>
              ) : (
                <>
                  <FileBarChart2 className="h-3.5 w-3.5" />
                  <span>Generate Report</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
