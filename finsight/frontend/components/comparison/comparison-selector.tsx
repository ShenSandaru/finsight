"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { DocumentResponse } from "@/types/api";
import { useDocuments } from "@/hooks/use-documents";
import { useUiStore } from "@/stores/ui-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Files,
  FileSpreadsheet,
  FileText,
  AlertCircle,
  CheckCircle2,
  X,
  Layers,
} from "lucide-react";

interface ComparisonSelectorProps {
  className?: string;
  onSelectionChange?: (selectedIds: string[]) => void;
}

/**
 * Institutional document comparison selection panel.
 * Reuses existing useUiStore.selectedDocumentIds.
 * Enforces minimum requirement of 2 documents.
 */
export function ComparisonSelector({
  className,
  onSelectionChange,
}: ComparisonSelectorProps) {
  const selectedDocumentIds = useUiStore((state) => state.selectedDocumentIds);
  const toggleDocumentSelection = useUiStore((state) => state.toggleDocumentSelection);
  const clearDocumentSelection = useUiStore((state) => state.clearDocumentSelection);
  const setSelectedDocumentIds = useUiStore((state) => state.setSelectedDocumentIds);

  const { data: documentsData, isLoading, isError, error } = useDocuments();
  const allDocs = documentsData?.documents || [];
  const indexedDocs = allDocs.filter((d) => d.status === "indexed");

  const selectedDocs = indexedDocs.filter((d) =>
    selectedDocumentIds.includes(d.id)
  );

  const meetsMinimum = selectedDocumentIds.length >= 2;

  const handleToggle = (id: string) => {
    toggleDocumentSelection(id);
    if (onSelectionChange) {
      const updated = selectedDocumentIds.includes(id)
        ? selectedDocumentIds.filter((docId) => docId !== id)
        : [...selectedDocumentIds, id];
      onSelectionChange(updated);
    }
  };

  const getFileIcon = (fileType: string) => {
    if (fileType.toLowerCase() === "csv") {
      return <FileSpreadsheet className="h-4 w-4 text-primary" aria-hidden="true" />;
    }
    return <FileText className="h-4 w-4 text-primary" aria-hidden="true" />;
  };

  return (
    <div
      className={cn("rounded-xl border bg-card p-4 sm:p-5 space-y-4 shadow-sm", className)}
      data-testid="comparison-selector"
    >
      {/* Selector Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b">
        <div>
          <div className="flex items-center gap-2">
            <Files className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold text-foreground">
              Comparison Document Scope
            </h2>
            <Badge
              variant={meetsMinimum ? "financePositive" : "secondary"}
              className="text-[11px] font-tabular-nums ml-1"
              data-testid="selected-count-badge"
            >
              {selectedDocumentIds.length} of {indexedDocs.length} selected
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Select 2 or more indexed corporate filings to compute cross-document financial variances and metric comparisons.
          </p>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          {selectedDocumentIds.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearDocumentSelection}
              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
              data-testid="clear-all-selection-btn"
            >
              Clear Selection
            </Button>
          )}
          {indexedDocs.length >= 2 && selectedDocumentIds.length < indexedDocs.length && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const allIndexedIds = indexedDocs.map((d) => d.id);
                setSelectedDocumentIds(allIndexedIds);
                if (onSelectionChange) onSelectionChange(allIndexedIds);
              }}
              className="h-7 px-2.5 text-xs"
              data-testid="select-all-indexed-btn"
            >
              Select All ({indexedDocs.length})
            </Button>
          )}
        </div>
      </div>

      {/* Selected Items Summary Strip */}
      {selectedDocs.length > 0 && (
        <div
          className="flex flex-wrap items-center gap-1.5 p-2 rounded-lg bg-muted/30 border text-xs"
          data-testid="selected-docs-summary"
        >
          <span className="text-[11px] font-semibold uppercase text-muted-foreground tracking-wider mr-1">
            Active Set:
          </span>
          {selectedDocs.map((doc, idx) => (
            <Badge
              key={doc.id}
              variant="secondary"
              className="gap-1.5 pl-2 pr-1 py-0.5 text-xs font-normal"
              data-testid={`selected-tag-${doc.id}`}
            >
              <span className="font-mono text-[10px] font-bold text-primary">
                Doc {String.fromCharCode(65 + idx)}:
              </span>
              <span className="max-w-[200px] truncate">
                {doc.title || doc.filename}
              </span>
              <button
                type="button"
                onClick={() => handleToggle(doc.id)}
                className="rounded-full p-0.5 hover:bg-muted text-muted-foreground hover:text-foreground"
                aria-label={`Remove ${doc.title || doc.filename}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {/* Minimum Selection Advisory Banner */}
      {!meetsMinimum && (
        <div
          className="flex items-center gap-2 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 text-xs"
          role="status"
          data-testid="minimum-selection-warning"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-500" />
          <span>
            {selectedDocumentIds.length === 0
              ? "Select at least 2 documents to compare."
              : "Select at least 1 more document to enable cross-document comparison."}
          </span>
        </div>
      )}

      {/* Document Grid / List */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 pt-1">
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
        </div>
      ) : isError ? (
        <div className="p-4 rounded-lg border border-destructive/20 bg-destructive/5 text-center text-xs text-destructive">
          Failed to load documents: {error?.message || "Repository communication error"}
        </div>
      ) : indexedDocs.length === 0 ? (
        <div className="p-6 rounded-lg border border-dashed text-center text-xs text-muted-foreground">
          No indexed documents available for comparison. Please upload and index filings in the Documents section first.
        </div>
      ) : (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-[300px] overflow-y-auto pr-1"
          data-testid="document-selection-grid"
        >
          {indexedDocs.map((doc) => {
            const isSelected = selectedDocumentIds.includes(doc.id);
            return (
              <div
                key={doc.id}
                onClick={() => handleToggle(doc.id)}
                className={cn(
                  "flex items-start gap-3 p-3 rounded-lg border text-left cursor-pointer transition-all select-none",
                  isSelected
                    ? "border-primary bg-primary/5 shadow-xs ring-1 ring-primary/40"
                    : "border-border bg-card hover:bg-muted/40 hover:border-muted-foreground/30"
                )}
                role="checkbox"
                aria-checked={isSelected}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === " " || e.key === "Enter") {
                    e.preventDefault();
                    handleToggle(doc.id);
                  }
                }}
                data-testid={`doc-checkbox-card-${doc.id}`}
              >
                <Checkbox
                  checked={isSelected}
                  onCheckedChange={() => handleToggle(doc.id)}
                  className="mt-0.5 pointer-events-none"
                  tabIndex={-1}
                  aria-hidden="true"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    {getFileIcon(doc.file_type)}
                    <p className="text-xs font-semibold text-foreground truncate" title={doc.title || doc.filename}>
                      {doc.title || doc.filename}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5 text-[11px] text-muted-foreground">
                    <span className="uppercase font-mono font-medium">{doc.file_type}</span>
                    <span>•</span>
                    <span className="flex items-center gap-0.5 font-tabular-nums">
                      <Layers className="h-3 w-3" />
                      {doc.total_chunks ?? 0} chunks
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
