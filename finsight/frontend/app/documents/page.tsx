"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { DocumentUploadZone } from "@/components/documents/document-upload-zone";
import { DocumentTable } from "@/components/documents/document-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import Link from "next/link";
import {
  Upload,
  Files,
  CheckCircle2,
  Loader2,
  AlertCircle,
  RefreshCw,
  FolderOpen,
  Filter,
  GitCompare,
} from "lucide-react";
import { useDocuments } from "@/hooks/use-documents";
import { useUiStore } from "@/stores/ui-store";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function DocumentsPage() {
  const [showUploadZone, setShowUploadZone] = useState(false);
  const [filterType, setFilterType] = useState<string>("all");

  const {
    data: documentData,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useDocuments();

  const selectedDocumentIds = useUiStore((state) => state.selectedDocumentIds);
  const clearDocumentSelection = useUiStore((state) => state.clearDocumentSelection);

  const documents = documentData?.documents || [];
  const totalDocs = documents.length;
  const indexedDocs = documents.filter((d) => d.status === "indexed").length;
  const processingDocs = documents.filter(
    (d) => d.status === "pending" || d.status === "processing"
  ).length;

  const filteredDocs = documents.filter((doc) => {
    if (filterType === "all") return true;
    if (filterType === "indexed") return doc.status === "indexed";
    if (filterType === "processing")
      return doc.status === "pending" || doc.status === "processing";
    if (filterType === "failed") return doc.status === "failed";
    return true;
  });

  return (
    <AuthGuard>
      <AppShell>
        <div className="space-y-6" data-testid="documents-page">
        {/* Workspace Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded bg-primary/10 text-primary">
                <Files className="h-4 w-4" />
              </div>
              <h1 className="text-xl font-bold tracking-tight text-foreground">
                Document Repository
              </h1>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Upload and manage financial statements (SEC 10-K, 10-Q, CSV, TXT) for grounded vector retrieval and multi-agent research.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
              className="gap-1.5 h-8 text-xs"
              title="Refresh repository"
              data-testid="refresh-docs-btn"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`}
              />
              <span>Refresh</span>
            </Button>

            <Button
              size="sm"
              onClick={() => setShowUploadZone((prev) => !prev)}
              className="gap-1.5 h-8 text-xs"
              data-testid="toggle-upload-btn"
            >
              <Upload className="h-3.5 w-3.5" />
              <span>{showUploadZone ? "Close Upload" : "Upload Filing"}</span>
            </Button>
          </div>
        </div>

        {/* Upload Zone (Collapsible / Expandable) */}
        {showUploadZone && (
          <div className="animate-in fade-in-50 duration-150">
            <DocumentUploadZone
              onUploadSuccess={() => {
                // Keep open or let user see progress
              }}
            />
          </div>
        )}

        {/* Repository Metric Summary Cards */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Card className="shadow-sm">
            <CardContent className="p-3.5 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Total Filings
                </p>
                <p className="text-lg font-bold font-tabular-nums text-foreground mt-0.5">
                  {isLoading ? "—" : totalDocs}
                </p>
              </div>
              <Files className="h-4 w-4 text-muted-foreground/60" />
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardContent className="p-3.5 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Indexed & Ready
                </p>
                <p className="text-lg font-bold font-tabular-nums text-finance-positive mt-0.5">
                  {isLoading ? "—" : indexedDocs}
                </p>
              </div>
              <CheckCircle2 className="h-4 w-4 text-finance-positive/80" />
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardContent className="p-3.5 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Processing
                </p>
                <p className="text-lg font-bold font-tabular-nums text-finance-warning mt-0.5">
                  {isLoading ? "—" : processingDocs}
                </p>
              </div>
              <Loader2
                className={`h-4 w-4 text-finance-warning/80 ${
                  processingDocs > 0 ? "animate-spin" : ""
                }`}
              />
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardContent className="p-3.5 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Active Context
                </p>
                <p className="text-lg font-bold font-tabular-nums text-primary mt-0.5">
                  {selectedDocumentIds.length}
                </p>
              </div>
              {selectedDocumentIds.length > 0 ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearDocumentSelection}
                  className="h-6 px-1.5 text-[10px] text-muted-foreground hover:text-foreground"
                  title="Clear active context"
                  data-testid="clear-selection-btn"
                >
                  Clear
                </Button>
              ) : null}
            </CardContent>
          </Card>
        </div>

        {/* Content View: Loading / Error / Empty / Table */}
        {isLoading ? (
          <div className="space-y-3" data-testid="documents-loading-skeleton">
            <div className="flex items-center justify-between">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-8 w-32" />
            </div>
            <Card className="overflow-hidden">
              <div className="p-4 space-y-3">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            </Card>
          </div>
        ) : isError ? (
          <Card
            className="border-destructive/40 bg-destructive/5"
            data-testid="documents-error-state"
          >
            <CardContent className="p-8 text-center space-y-3">
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-destructive/15 text-destructive">
                <AlertCircle className="h-5 w-5" />
              </div>
              <h2 className="text-sm font-semibold text-foreground">
                Failed to load document repository
              </h2>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                {error?.message ||
                  "Unable to communicate with the FinSight backend API. Please ensure the backend service is running."}
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => refetch()}
                className="mt-2 text-xs"
              >
                Try Again
              </Button>
            </CardContent>
          </Card>
        ) : documents.length === 0 ? (
          <Card data-testid="documents-empty-state">
            <CardContent className="p-12 text-center space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <FolderOpen className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h2 className="text-base font-semibold text-foreground">
                  No documents in repository
                </h2>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  Upload financial filings such as 10-K, 10-Q statements, earnings call transcripts, or financial CSV files to enable vector similarity search and grounded multi-agent research.
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => setShowUploadZone(true)}
                className="gap-1.5 text-xs"
                data-testid="empty-state-upload-btn"
              >
                <Upload className="h-3.5 w-3.5" />
                <span>Upload Your First Filing</span>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {/* Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Filter className="h-3.5 w-3.5" />
                <span>Filter status:</span>
                <div className="flex items-center gap-1">
                  {(["all", "indexed", "processing", "failed"] as const).map((type) => (
                    <Button
                      key={type}
                      variant={filterType === type ? "secondary" : "ghost"}
                      size="sm"
                      onClick={() => setFilterType(type)}
                      className="h-6 px-2 text-[11px] capitalize"
                      data-testid={`filter-${type}`}
                    >
                      {type}
                    </Button>
                  ))}
                </div>
              </div>

              {selectedDocumentIds.length > 0 && (
                <div className="flex items-center gap-2">
                  <Badge variant="financePositive" className="text-xs px-2 py-0.5">
                    {selectedDocumentIds.length} filing{selectedDocumentIds.length > 1 ? "s" : ""} selected
                  </Badge>

                  {selectedDocumentIds.length >= 2 && (
                    <Link href="/compare">
                      <Button
                        size="sm"
                        className="h-6 px-2.5 text-xs gap-1.5 font-semibold"
                        data-testid="compare-selected-docs-btn"
                      >
                        <GitCompare className="h-3 w-3" />
                        <span>Compare Filings ({selectedDocumentIds.length})</span>
                      </Button>
                    </Link>
                  )}

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearDocumentSelection}
                    className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                  >
                    Clear
                  </Button>
                </div>
              )}
            </div>

            {/* Document Table */}
            <DocumentTable documents={filteredDocs} />
          </div>
        )}
      </div>
    </AppShell>
  </AuthGuard>
  );
}
