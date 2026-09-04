"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { ReportStatusBadge } from "@/components/reports/report-status-badge";
import { ReportViewer } from "@/components/reports/report-viewer";
import { FindingList } from "@/components/finance/finding-list";
import { CitationDrawer } from "@/components/citations/citation-drawer";
import { useReport, useDeleteReport } from "@/hooks/use-reports";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  FileBarChart2,
  ChevronLeft,
  Download,
  Copy,
  Check,
  Trash2,
  AlertCircle,
  Clock,
  Layers,
  Calendar,
  Loader2,
  RotateCw,
  ExternalLink,
} from "lucide-react";
import type { FinancialFinding } from "@/types/api";

export default function ReportDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reportId = String(params?.reportId || "");

  const {
    data: report,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useReport(reportId);

  const { mutate: deleteReport, isPending: isDeleting } = useDeleteReport();

  const [copied, setCopied] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleExportMarkdown = () => {
    if (!report?.content) return;

    const safeTitle = (report.title || "financial-report")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");

    const blob = new Blob([report.content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${safeTitle}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopyMarkdown = async () => {
    if (!report?.content) return;
    try {
      await navigator.clipboard.writeText(report.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard write fallback
    }
  };

  const handleDelete = () => {
    deleteReport(reportId, {
      onSuccess: () => {
        router.push("/reports");
      },
    });
  };

  const formatTimestamp = (iso?: string) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  // Check if findings match FinancialFinding contract
  const validFindings: FinancialFinding[] = React.useMemo(() => {
    if (!report?.findings || !Array.isArray(report.findings)) return [];
    return report.findings.filter(
      (f): f is FinancialFinding =>
        typeof f === "object" &&
        f !== null &&
        "metric" in f &&
        "period" in f &&
        "value" in f
    );
  }, [report?.findings]);

  return (
    <AppShell>
      <div
        className="max-w-5xl mx-auto space-y-6 pb-16 px-4 sm:px-6"
        data-testid="report-detail-page"
      >
        {/* Navigation Breadcrumb & Back */}
        <div className="flex items-center justify-between pt-2">
          <Link
            href="/reports"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors font-medium"
            data-testid="back-to-reports-link"
          >
            <ChevronLeft className="h-4 w-4" />
            <span>All Research Reports</span>
          </Link>

          <div className="flex items-center gap-2">
            <Link href="/research">
              <Button variant="ghost" size="sm" className="text-xs gap-1.5 h-8">
                <ExternalLink className="h-3.5 w-3.5" />
                <span>Research Workspace</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="space-y-6" data-testid="report-detail-loading">
            <div className="rounded-xl border bg-card p-6 space-y-4 shadow-sm">
              <Skeleton className="h-6 w-1/3" />
              <Skeleton className="h-4 w-2/3" />
              <div className="flex gap-3 pt-2">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-5 w-20" />
              </div>
            </div>
            <Skeleton className="h-96 w-full rounded-xl" />
          </div>
        )}

        {/* Error / Not Found State */}
        {isError && !isLoading && (
          <div
            className="rounded-xl border border-destructive/20 bg-destructive/5 p-8 text-center space-y-3"
            role="alert"
            data-testid="report-detail-error"
          >
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <AlertCircle className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-foreground">
                Unable to Load Report
              </h3>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                {error?.message || "The requested financial research report could not be found or retrieved."}
              </p>
            </div>
            <div className="pt-2 flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
                className="text-xs gap-1.5"
              >
                <RotateCw className="h-3.5 w-3.5" />
                <span>Retry</span>
              </Button>
              <Link href="/reports">
                <Button variant="secondary" size="sm" className="text-xs">
                  Return to Reports
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* Report Content when loaded */}
        {!isLoading && !isError && report && (
          <div className="space-y-6">
            {/* Header Card */}
            <div className="rounded-xl border bg-card p-5 sm:p-6 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div className="space-y-1.5 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <ReportStatusBadge status={report.status} />
                    <Badge variant="secondary" className="text-[10px] font-mono capitalize">
                      {report.report_type.replace(/_/g, " ")}
                    </Badge>
                  </div>
                  <h1
                    className="text-xl sm:text-2xl font-bold tracking-tight text-foreground"
                    data-testid="report-detail-title"
                  >
                    {report.title}
                  </h1>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    <span className="font-semibold text-foreground">Query: </span>
                    {report.query}
                  </p>
                </div>

                {/* Header Action Buttons */}
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  {report.status === "completed" && report.content && (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopyMarkdown}
                        className="text-xs gap-1.5 h-8"
                        data-testid="copy-markdown-btn"
                        title="Copy Markdown to clipboard"
                      >
                        {copied ? (
                          <>
                            <Check className="h-3.5 w-3.5 text-finance-positive" />
                            <span className="text-finance-positive">Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            <span>Copy</span>
                          </>
                        )}
                      </Button>

                      <Button
                        variant="default"
                        size="sm"
                        onClick={handleExportMarkdown}
                        className="text-xs gap-1.5 h-8"
                        data-testid="export-markdown-btn"
                      >
                        <Download className="h-3.5 w-3.5" />
                        <span>Export Markdown</span>
                      </Button>
                    </>
                  )}

                  {!showDeleteConfirm ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDeleteConfirm(true)}
                      className="text-xs text-muted-foreground hover:text-destructive h-8 px-2"
                      title="Delete Report"
                      data-testid="delete-report-btn"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  ) : (
                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={handleDelete}
                        disabled={isDeleting}
                        className="text-xs h-8"
                        data-testid="confirm-delete-report-btn"
                      >
                        {isDeleting ? "Deleting..." : "Confirm"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowDeleteConfirm(false)}
                        className="text-xs h-8 px-2"
                      >
                        Cancel
                      </Button>
                    </div>
                  )}
                </div>
              </div>

              {/* Metadata strip */}
              <div className="flex flex-wrap items-center gap-y-2 gap-x-5 pt-3 border-t text-xs text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5 text-primary/70" />
                  <span>Created {formatTimestamp(report.created_at)}</span>
                </div>

                <div className="flex items-center gap-1.5">
                  <Layers className="h-3.5 w-3.5 text-primary/70" />
                  <span>
                    {report.document_ids && report.document_ids.length > 0
                      ? `${report.document_ids.length} Scoped Filing${report.document_ids.length > 1 ? "s" : ""}`
                      : "Repository Wide"}
                  </span>
                </div>

                {report.citations && report.citations.length > 0 && (
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-foreground font-semibold">
                      {report.citations.length}
                    </span>
                    <span>Evidence Citations</span>
                  </div>
                )}
              </div>
            </div>

            {/* Pending or Processing Terminal State */}
            {(report.status === "pending" || report.status === "processing") && (
              <div
                className="rounded-xl border bg-card/60 p-8 text-center space-y-4 shadow-sm"
                data-testid="report-processing-state"
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/10 text-blue-500 animate-pulse">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
                <div className="space-y-1.5 max-w-md mx-auto">
                  <h3 className="text-base font-semibold text-foreground">
                    Financial Report Generation in Progress
                  </h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    FinSight multi-agent research DAG is currently executing vector retrieval,
                    auditing financial ratios, and deterministically compiling publication Markdown.
                  </p>
                </div>
                <div className="flex items-center justify-center gap-2 pt-2">
                  <Badge variant="outline" className="text-xs font-mono gap-1.5 py-1 px-3">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>Auto-refreshing status live...</span>
                  </Badge>
                </div>
              </div>
            )}

            {/* Failed State */}
            {report.status === "failed" && (
              <div
                className="rounded-xl border border-destructive/20 bg-destructive/5 p-6 space-y-3"
                role="alert"
                data-testid="report-failed-state"
              >
                <div className="flex items-center gap-2 text-destructive">
                  <AlertCircle className="h-5 w-5 shrink-0" />
                  <h3 className="text-sm font-semibold">
                    Report Generation Failed
                  </h3>
                </div>
                <p className="text-xs text-muted-foreground">
                  {report.error_message ||
                    "An error occurred during report synthesis or guardrails verification. Please try generating a new report."}
                </p>
              </div>
            )}

            {/* Completed Report Body */}
            {report.status === "completed" && (
              <div className="space-y-6">
                {/* Structured Financial Findings if present and compatible */}
                {validFindings.length > 0 && (
                  <div className="rounded-xl border bg-card p-5 shadow-sm">
                    <FindingList findings={validFindings} />
                  </div>
                )}

                {/* Full Markdown Report Content */}
                {report.content ? (
                  <div className="rounded-xl border bg-card p-6 sm:p-8 shadow-sm">
                    <ReportViewer
                      content={report.content}
                      citations={report.citations}
                    />
                  </div>
                ) : (
                  <div className="rounded-xl border bg-muted/20 p-8 text-center text-xs text-muted-foreground">
                    No Markdown content recorded for this report.
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Mount CitationDrawer for instant evidence inspection (Phase 11.5) */}
      <CitationDrawer />
    </AppShell>
  );
}
