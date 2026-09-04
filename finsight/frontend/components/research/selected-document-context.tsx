"use client";

import React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Files, ExternalLink, X, GitCompare } from "lucide-react";
import { useUiStore } from "@/stores/ui-store";
import { useDocuments } from "@/hooks/use-documents";

interface SelectedDocumentContextProps {
  className?: string;
}

export function SelectedDocumentContext({ className }: SelectedDocumentContextProps) {
  const selectedDocumentIds = useUiStore((state) => state.selectedDocumentIds);
  const toggleDocumentSelection = useUiStore((state) => state.toggleDocumentSelection);
  const clearDocumentSelection = useUiStore((state) => state.clearDocumentSelection);

  const { data: documentData } = useDocuments();
  const allDocs = documentData?.documents || [];

  const selectedDocs = allDocs.filter((d) => selectedDocumentIds.includes(d.id));

  if (selectedDocumentIds.length === 0) {
    return (
      <div
        className={`flex flex-wrap items-center justify-between gap-2 rounded-md border border-dashed border-muted-foreground/30 bg-muted/20 px-3 py-2 text-xs ${className ?? ""}`}
        data-testid="selected-document-context-empty"
      >
        <div className="flex items-center gap-2 text-muted-foreground">
          <Files className="h-3.5 w-3.5 text-muted-foreground/70 shrink-0" />
          <span>
            Researching across <span className="font-medium text-foreground">all repository filings</span> (no filter).
          </span>
        </div>
        <Link href="/documents">
          <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1 text-primary hover:text-primary">
            <span>Select Specific Filings</span>
            <ExternalLink className="h-3 w-3" />
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div
      className={`rounded-md border bg-card p-2.5 space-y-2 ${className ?? ""}`}
      data-testid="selected-document-context"
    >
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 font-medium text-foreground">
          <Files className="h-3.5 w-3.5 text-primary" />
          <span>Research Scoped Context</span>
          <Badge variant="financePositive" className="text-[10px] h-4 px-1.5 py-0 font-tabular-nums">
            {selectedDocumentIds.length} filing{selectedDocumentIds.length > 1 ? "s" : ""}
          </Badge>
        </div>

        <div className="flex items-center gap-1">
          {selectedDocumentIds.length >= 2 && (
            <Link href="/compare">
              <Button
                variant="ghost"
                size="sm"
                className="h-5 px-1.5 text-[11px] text-primary hover:text-primary gap-1 font-medium"
                data-testid="research-compare-shortcut-btn"
              >
                <GitCompare className="h-3 w-3" />
                <span>Compare</span>
              </Button>
            </Link>
          )}
          <Link href="/documents">
            <Button variant="ghost" size="sm" className="h-5 px-1.5 text-[11px] text-muted-foreground hover:text-foreground">
              Manage
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearDocumentSelection}
            className="h-5 px-1.5 text-[11px] text-muted-foreground hover:text-destructive"
            data-testid="clear-context-docs-btn"
          >
            Clear
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
        {selectedDocumentIds.map((id) => {
          const doc = allDocs.find((d) => d.id === id);
          const displayLabel = doc?.title || doc?.filename || id;

          return (
            <Badge
              key={id}
              variant="secondary"
              className="gap-1 pl-2 pr-1 py-0.5 text-xs font-normal max-w-[260px] truncate"
              title={displayLabel}
            >
              <span className="truncate">{displayLabel}</span>
              <button
                type="button"
                onClick={() => toggleDocumentSelection(id)}
                className="rounded-full p-0.5 hover:bg-muted text-muted-foreground hover:text-foreground"
                aria-label={`Deselect ${displayLabel}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          );
        })}
      </div>
    </div>
  );
}
