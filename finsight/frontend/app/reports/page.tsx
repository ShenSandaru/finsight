"use client";

import React, { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { ReportStatusBadge } from "@/components/reports/report-status-badge";
import { GenerateReportModal } from "@/components/reports/generate-report-modal";
import { useReports, useDeleteReport } from "@/hooks/use-reports";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  FileBarChart2,
  Plus,
  Trash2,
  ExternalLink,
  RotateCw,
  Search,
  Filter,
  Layers,
  Calendar,
  AlertCircle,
  Clock,
} from "lucide-react";
import type { ReportStatus, ReportResponse } from "@/types/api";

const STATUS_FILTERS: Array<{ label: string; value: ReportStatus | "all" }> = [
  { label: "All Reports", value: "all" },
  { label: "Completed", value: "completed" },
  { label: "Processing", value: "processing" },
  { label: "Pending", value: "pending" },
  { label: "Failed", value: "failed" },
];

export default function ReportsHistoryPage() {
  const [statusFilter, setStatusFilter] = useState<ReportStatus | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const queryParams = {
    status: statusFilter === "all" ? undefined : statusFilter,
    limit: 50,
  };

  const {
    data: reportsData,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useReports(queryParams);

  const { mutate: deleteReport, isPending: isDeleting } = useDeleteReport();

  const reports = reportsData?.reports || [];

  // Filter client-side by search query if user searches title or query text
  const filteredReports = reports.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      r.title.toLowerCase().includes(q) ||
      r.query.toLowerCase().includes(q)
    );
  });

  const handleDelete = (reportId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (confirm("Are you sure you want to delete this research report? Source documents will not be deleted.")) {
      setDeletingId(reportId);
      deleteReport(reportId, {
        onSettled: () => setDeletingId(null),
      });
    }
  };

  const formatTimestamp = (iso?: string) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return iso;
    }
  };

  return (
    <AppShell>
      <div
        className="max-w-6xl mx-auto space-y-6 pb-16 px-4 sm:px-6"
        data-testid="reports-history-page"
      >
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2 border-b pb-5">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <FileBarChart2 className="h-4 w-4" />
              </div>
              <h1 className="text-xl font-bold tracking-tight text-foreground">
                Structured Research Reports
              </h1>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Deterministic, long-form financial research reports with executive summaries,
              verified metrics, and source citations.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
              className="text-xs h-9 gap-1.5"
              data-testid="refresh-reports-btn"
            >
              <RotateCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </Button>

            <Button
              size="sm"
              onClick={() => setIsGenerateModalOpen(true)}
              className="text-xs h-9 gap-1.5"
              data-testid="open-generate-report-modal-btn"
            >
              <Plus className="h-4 w-4" />
              <span>Generate Report</span>
            </Button>
          </div>
        </div>

        {/* Filters and Search Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Status Filter Tabs */}
          <div
            className="flex flex-wrap items-center gap-1.5 p-1 rounded-lg bg-muted/40 border text-xs"
            role="tablist"
            data-testid="status-filter-tabs"
          >
            {STATUS_FILTERS.map((tab) => {
              const active = statusFilter === tab.value;
              return (
                <button
                  key={tab.value}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setStatusFilter(tab.value)}
                  className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                    active
                      ? "bg-card text-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  data-testid={`filter-${tab.value}`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Search Input */}
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search reports..."
              className="w-full pl-8 pr-3 py-1.5 rounded-md border bg-background text-xs focus:outline-none focus:ring-2 focus:ring-ring"
              data-testid="search-reports-input"
            />
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="rounded-xl border bg-card p-6 space-y-4 shadow-sm" data-testid="reports-loading">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}

        {/* Error State */}
        {isError && !isLoading && (
          <div
            className="rounded-xl border border-destructive/20 bg-destructive/5 p-8 text-center space-y-3"
            role="alert"
            data-testid="reports-error"
          >
            <AlertCircle className="h-6 w-6 text-destructive mx-auto" />
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-foreground">
                Unable to Load Reports
              </h3>
              <p className="text-xs text-muted-foreground">
                {error?.message || "A network or server error occurred while retrieving research reports."}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="text-xs mt-2"
            >
              Retry
            </Button>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !isError && filteredReports.length === 0 && (
          <div
            className="rounded-xl border border-dashed p-12 text-center space-y-4 bg-card/40"
            data-testid="reports-empty-state"
          >
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <FileBarChart2 className="h-6 w-6" />
            </div>
            <div className="space-y-1.5 max-w-sm mx-auto">
              <h3 className="text-sm font-semibold text-foreground">
                No research reports yet
              </h3>
              <p className="text-xs text-muted-foreground">
                {searchQuery
                  ? `No reports matched "${searchQuery}".`
                  : statusFilter !== "all"
                  ? `No reports currently in "${statusFilter}" status.`
                  : "Generate a report from a research session to get started."}
              </p>
            </div>
            <div className="pt-2">
              <Button
                size="sm"
                onClick={() => setIsGenerateModalOpen(true)}
                className="text-xs gap-1.5"
                data-testid="empty-generate-report-btn"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Generate New Report</span>
              </Button>
            </div>
          </div>
        )}

        {/* Reports Table */}
        {!isLoading && !isError && filteredReports.length > 0 && (
          <div
            className="rounded-xl border bg-card overflow-hidden shadow-sm"
            data-testid="reports-table-container"
          >
            <div className="overflow-x-auto">
              <Table className="w-full text-xs">
                <TableHeader className="bg-muted/40 border-b">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="py-3 px-4 font-semibold text-foreground">
                      Report Title & Query
                    </TableHead>
                    <TableHead className="py-3 px-4 font-semibold text-foreground">
                      Status
                    </TableHead>
                    <TableHead className="py-3 px-4 font-semibold text-foreground">
                      Filing Scope
                    </TableHead>
                    <TableHead className="py-3 px-4 font-semibold text-foreground">
                      Created
                    </TableHead>
                    <TableHead className="py-3 px-4 text-right font-semibold text-foreground">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredReports.map((report) => (
                    <TableRow
                      key={report.id}
                      className="hover:bg-muted/30 transition-colors border-b last:border-b-0 group cursor-pointer"
                      onClick={() => {
                        window.location.href = `/reports/${report.id}`;
                      }}
                      data-testid={`report-row-${report.id}`}
                    >
                      <TableCell className="py-3 px-4 max-w-xs sm:max-w-md">
                        <div className="space-y-0.5">
                          <Link
                            href={`/reports/${report.id}`}
                            className="font-semibold text-foreground hover:text-primary transition-colors line-clamp-1 block"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {report.title}
                          </Link>
                          <p className="text-[11px] text-muted-foreground line-clamp-1">
                            {report.query}
                          </p>
                        </div>
                      </TableCell>

                      <TableCell className="py-3 px-4 whitespace-nowrap">
                        <ReportStatusBadge status={report.status} />
                      </TableCell>

                      <TableCell className="py-3 px-4 whitespace-nowrap text-muted-foreground">
                        <div className="flex items-center gap-1.5 font-mono text-[11px]">
                          <Layers className="h-3 w-3 text-primary/70" />
                          <span>
                            {report.document_ids && report.document_ids.length > 0
                              ? `${report.document_ids.length} docs`
                              : "All Docs"}
                          </span>
                        </div>
                      </TableCell>

                      <TableCell className="py-3 px-4 whitespace-nowrap text-muted-foreground font-mono text-[11px]">
                        {formatTimestamp(report.created_at)}
                      </TableCell>

                      <TableCell className="py-3 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1">
                          <Link href={`/reports/${report.id}`} onClick={(e) => e.stopPropagation()}>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs gap-1 text-primary hover:text-primary hover:bg-primary/10"
                              title="View Report"
                            >
                              <span>View</span>
                              <ExternalLink className="h-3 w-3" />
                            </Button>
                          </Link>

                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => handleDelete(report.id, e)}
                            disabled={isDeleting && deletingId === report.id}
                            className="h-7 px-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            title="Delete Report"
                            data-testid={`delete-report-btn-${report.id}`}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        {/* Generate Report Modal */}
        <GenerateReportModal
          open={isGenerateModalOpen}
          onOpenChange={setIsGenerateModalOpen}
        />
      </div>
    </AppShell>
  );
}
