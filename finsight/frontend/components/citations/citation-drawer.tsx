"use client";

import React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  X,
  FileText,
  Table as TableIcon,
  Layers,
  Calendar,
  FileSpreadsheet,
  AlertTriangle,
  RotateCw,
  ExternalLink,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useUiStore } from "@/stores/ui-store";
import { useCitationChunk } from "@/hooks/use-documents";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/**
 * Parser for standard Markdown tables into rows and columns
 */
function parseMarkdownTable(markdown: string): {
  headers: string[];
  alignments: Array<"left" | "center" | "right">;
  rows: string[][];
} | null {
  const lines = markdown
    .trim()
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  if (lines.length < 2) return null;

  // Find header row and separator row
  const headerLine = lines[0];
  const separatorLine = lines[1];

  if (!headerLine.includes("|") || !separatorLine.includes("|")) {
    return null;
  }

  // Parse headers
  const headers = headerLine
    .split("|")
    .map((cell) => cell.trim())
    .filter((_, idx, arr) => (idx === 0 && arr[0] === "" ? false : idx === arr.length - 1 && arr[arr.length - 1] === "" ? false : true));

  // Parse alignments from separator line (e.g. :---, :---:, ---:)
  const rawAligns = separatorLine
    .split("|")
    .map((cell) => cell.trim())
    .filter((_, idx, arr) => (idx === 0 && arr[0] === "" ? false : idx === arr.length - 1 && arr[arr.length - 1] === "" ? false : true));

  const alignments = rawAligns.map((align): "left" | "center" | "right" => {
    const starts = align.startsWith(":");
    const ends = align.endsWith(":");
    if (starts && ends) return "center";
    if (ends) return "right";
    return "left";
  });

  // Parse data rows
  const rows: string[][] = [];
  for (let i = 2; i < lines.length; i++) {
    const line = lines[i];
    if (!line.includes("|")) continue;

    const rowCells = line
      .split("|")
      .map((c) => c.trim())
      .filter((_, idx, arr) => (idx === 0 && arr[0] === "" ? false : idx === arr.length - 1 && arr[arr.length - 1] === "" ? false : true));

    rows.push(rowCells);
  }

  return { headers, alignments, rows };
}

/**
 * Renders table content: either parsed Markdown table or formatted pre block fallback
 */
function TableEvidenceViewer({ content }: { content: string }) {
  const parsed = parseMarkdownTable(content);

  if (!parsed || parsed.headers.length === 0) {
    return (
      <div className="rounded-md border bg-muted/20 p-3 overflow-x-auto">
        <pre className="text-xs font-mono whitespace-pre text-foreground/90">
          {content}
        </pre>
      </div>
    );
  }

  return (
    <div
      className="rounded-md border bg-card overflow-hidden shadow-xs"
      data-testid="citation-table-container"
    >
      <div className="overflow-x-auto max-h-[500px]">
        <Table className="w-full text-xs">
          <TableHeader className="bg-muted/50 sticky top-0 z-10 border-b">
            <TableRow>
              {parsed.headers.map((header, idx) => (
                <TableHead
                  key={`th-${idx}`}
                  className={cn(
                    "text-xs font-semibold py-2 px-3 whitespace-nowrap text-foreground",
                    parsed.alignments[idx] === "right"
                      ? "text-right"
                      : parsed.alignments[idx] === "center"
                      ? "text-center"
                      : "text-left"
                  )}
                >
                  {header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {parsed.rows.map((row, rowIdx) => (
              <TableRow
                key={`tr-${rowIdx}`}
                className="hover:bg-muted/30 transition-colors border-b last:border-b-0"
              >
                {parsed.headers.map((_, colIdx) => {
                  const cellValue = row[colIdx] || "";
                  const align = parsed.alignments[colIdx] || "left";
                  const isNegative =
                    /^\(.*\)$/.test(cellValue) || /^-\$?\d/.test(cellValue);

                  return (
                    <TableCell
                      key={`td-${rowIdx}-${colIdx}`}
                      className={cn(
                        "py-2 px-3 whitespace-nowrap font-tabular-nums text-xs",
                        align === "right"
                          ? "text-right"
                          : align === "center"
                          ? "text-center"
                          : "text-left",
                        isNegative && "text-finance-negative font-medium"
                      )}
                    >
                      {cellValue}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

/**
 * Citation & Evidence Inspector Slide-Over Drawer (Phase 11.5)
 */
export function CitationDrawer() {
  const isOpen = useUiStore((state) => state.citationDrawerOpen);
  const activeChunkId = useUiStore((state) => state.activeCitationChunkId);
  const activeContext = useUiStore((state) => state.activeCitationContext);
  const closeDrawer = useUiStore((state) => state.closeCitationDrawer);

  const {
    data: chunk,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useCitationChunk(activeChunkId);

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      closeDrawer();
    }
  };

  const sourceNumber = activeContext?.sourceNumber || "1";
  const similarityScore = activeContext?.similarity ?? (chunk?.metadata?.similarity as number | undefined);
  const isTable = (chunk?.chunk_type || "").toLowerCase() === "table";

  return (
    <DialogPrimitive.Root open={isOpen} onOpenChange={handleOpenChange}>
      <DialogPrimitive.Portal>
        {/* Overlay backdrop */}
        <DialogPrimitive.Overlay
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs transition-opacity duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
          data-testid="citation-drawer-overlay"
        />

        {/* Slide-over panel */}
        <DialogPrimitive.Content
          className={cn(
            "fixed inset-y-0 right-0 z-50 flex h-full w-full flex-col border-l bg-background shadow-2xl transition ease-in-out duration-300 sm:max-w-xl md:max-w-2xl lg:max-w-2xl",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right"
          )}
          aria-describedby="citation-drawer-description"
          data-testid="citation-drawer-content"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b px-5 py-3.5 bg-card/80 backdrop-blur-xs shrink-0">
            <div className="flex items-center gap-2.5">
              <Badge
                variant="outline"
                className="font-mono text-[11px] px-2 py-0.5 border-primary/30 bg-primary/10 text-primary font-semibold"
                data-testid="citation-drawer-source-badge"
              >
                SOURCE {sourceNumber}
              </Badge>
              <div>
                <DialogPrimitive.Title className="text-sm font-semibold text-foreground tracking-tight">
                  Evidence Inspector
                </DialogPrimitive.Title>
                <DialogPrimitive.Description
                  id="citation-drawer-description"
                  className="text-[11px] text-muted-foreground"
                >
                  Inspect authoritative filing provenance and underlying chunk evidence
                </DialogPrimitive.Description>
              </div>
            </div>

            <DialogPrimitive.Close
              className="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
              aria-label="Close evidence inspector"
              data-testid="citation-drawer-close-button"
            >
              <X className="h-4 w-4" />
            </DialogPrimitive.Close>
          </div>

          {/* Drawer Body Area */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Loading State */}
            {isLoading && (
              <div
                className="space-y-5"
                data-testid="citation-drawer-loading"
                role="status"
                aria-label="Loading source evidence"
              >
                <div className="rounded-lg border bg-card/50 p-4 space-y-3">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-6 w-full" />
                  <div className="flex gap-2 pt-1">
                    <Skeleton className="h-5 w-20" />
                    <Skeleton className="h-5 w-24" />
                    <Skeleton className="h-5 w-16" />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                  <Skeleton className="h-40 w-full rounded-md" />
                </div>
              </div>
            )}

            {/* Error State */}
            {isError && !isLoading && (
              <div
                className="flex flex-col items-center justify-center p-8 text-center rounded-lg border border-destructive/20 bg-destructive/5 space-y-3"
                role="alert"
                data-testid="citation-drawer-error"
              >
                <div className="rounded-full bg-destructive/10 p-2.5 text-destructive">
                  <AlertTriangle className="h-5 w-5" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-foreground">
                    Unable to load source evidence
                  </h4>
                  <p className="text-xs text-muted-foreground max-w-sm">
                    {error?.message ||
                      "The requested evidence chunk could not be retrieved from the indexing repository."}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => refetch()}
                  disabled={isFetching}
                  className="gap-1.5 h-8 text-xs mt-2"
                  data-testid="citation-drawer-retry-button"
                >
                  <RotateCw
                    className={cn("h-3.5 w-3.5", isFetching && "animate-spin")}
                  />
                  <span>Retry</span>
                </Button>
              </div>
            )}

            {/* Content Display */}
            {!isLoading && !isError && chunk && (
              <div className="space-y-5" data-testid="citation-drawer-body">
                {/* Provenance & Metadata Card */}
                <div className="rounded-lg border bg-card p-4 space-y-3 shadow-2xs">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1 min-w-0">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block">
                        Filing Document
                      </span>
                      <h3
                        className="text-sm font-semibold text-foreground truncate"
                        title={chunk.document_title || chunk.document_filename || "Document"}
                        data-testid="citation-doc-title"
                      >
                        {chunk.document_title || chunk.document_filename || "Untitled Document"}
                      </h3>
                      {chunk.document_filename && chunk.document_title && (
                        <p className="text-xs text-muted-foreground font-mono truncate">
                          {chunk.document_filename}
                        </p>
                      )}
                    </div>

                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[10px] uppercase font-mono tracking-wider font-semibold shrink-0 gap-1 px-2 py-0.5",
                        isTable
                          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          : "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400"
                      )}
                      data-testid="citation-chunk-type-badge"
                    >
                      {isTable ? (
                        <TableIcon className="h-3 w-3" />
                      ) : (
                        <FileText className="h-3 w-3" />
                      )}
                      <span>{isTable ? "TABLE" : "TEXT"}</span>
                    </Badge>
                  </div>

                  {/* Metadata Chips Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t text-xs">
                    {chunk.page_number !== null && chunk.page_number !== undefined && (
                      <div className="space-y-0.5">
                        <span className="text-[10px] uppercase text-muted-foreground block">
                          Page
                        </span>
                        <span
                          className="font-mono font-medium text-foreground"
                          data-testid="citation-page-number"
                        >
                          Page {chunk.page_number}
                        </span>
                      </div>
                    )}

                    {similarityScore !== undefined && similarityScore !== null && (
                      <div className="space-y-0.5">
                        <span className="text-[10px] uppercase text-muted-foreground block">
                          Relevance
                        </span>
                        <span
                          className="font-mono font-medium text-foreground"
                          data-testid="citation-similarity"
                        >
                          {(similarityScore * 100).toFixed(1)}% ({similarityScore.toFixed(3)})
                        </span>
                      </div>
                    )}

                    <div className="space-y-0.5">
                      <span className="text-[10px] uppercase text-muted-foreground block">
                        Chunk Index
                      </span>
                      <span className="font-mono font-medium text-foreground">
                        #{chunk.chunk_index}
                      </span>
                    </div>

                    {Boolean(chunk.metadata?.statement_type || activeContext?.statementType) && (
                      <div className="space-y-0.5">
                        <span className="text-[10px] uppercase text-muted-foreground block">
                          Statement
                        </span>
                        <span className="font-mono font-medium capitalize text-foreground truncate block">
                          {String(
                            chunk.metadata?.statement_type ||
                              activeContext?.statementType
                          ).replace(/_/g, " ")}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Optional Financial Table / Filing Section Info */}
                  {chunk.metadata && (
                    <div className="space-y-1.5 pt-2 border-t text-xs">
                      {Boolean(chunk.metadata.table_title) && (
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <BookOpen className="h-3.5 w-3.5 shrink-0 text-primary/70" />
                          <span className="font-medium text-foreground truncate">
                            {String(chunk.metadata.table_title)}
                          </span>
                        </div>
                      )}
                      {Boolean(chunk.metadata.section) && (
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Layers className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{String(chunk.metadata.section)}</span>
                        </div>
                      )}
                      {Array.isArray(chunk.metadata.fiscal_periods) &&
                        chunk.metadata.fiscal_periods.length > 0 && (
                          <div className="flex items-center gap-1.5 text-muted-foreground">
                            <Calendar className="h-3.5 w-3.5 shrink-0" />
                            <span>
                              Periods: {chunk.metadata.fiscal_periods.join(", ")}
                            </span>
                          </div>
                        )}
                    </div>
                  )}
                </div>

                {/* Retrieved Source Evidence Section */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Retrieved Source Evidence
                    </h4>
                    <span className="text-[10px] text-muted-foreground font-mono">
                      authoritative • unedited
                    </span>
                  </div>

                  {isTable ? (
                    <TableEvidenceViewer content={chunk.content} />
                  ) : (
                    <div
                      className="rounded-md border bg-card p-4 overflow-y-auto max-h-[500px] text-sm leading-relaxed select-text font-sans text-foreground/90 whitespace-pre-wrap shadow-2xs"
                      data-testid="citation-text-content"
                    >
                      {chunk.content}
                    </div>
                  )}
                </div>

                {/* Chunk ID & Provenance Trace Footer */}
                <div className="pt-2 border-t flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground font-mono">
                  <span title={chunk.id} data-testid="citation-chunk-id">
                    Chunk: {chunk.id}
                  </span>
                  <span title={chunk.document_id}>Doc: {chunk.document_id}</span>
                </div>
              </div>
            )}

            {/* Empty / Missing Chunk Fallback */}
            {!isLoading && !isError && !chunk && (
              <div
                className="flex flex-col items-center justify-center p-8 text-center rounded-lg border border-dashed text-muted-foreground space-y-2"
                data-testid="citation-drawer-empty"
              >
                <BookOpen className="h-6 w-6 stroke-1" />
                <p className="text-xs font-medium">
                  Source evidence is currently unavailable.
                </p>
                <p className="text-[11px]">
                  No chunk matching identifier was found in the indexed filing repository.
                </p>
              </div>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
