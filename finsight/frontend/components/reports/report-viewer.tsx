"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { CitationPill } from "@/components/research/citation-pill";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CitationResponse } from "@/types/api";

interface ReportViewerProps {
  content: string;
  citations?: CitationResponse[] | null;
  className?: string;
}

/**
 * Parses Markdown tables into headers, alignments, and cell rows.
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

  if (headers.length === 0) return null;

  // Parse alignments
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

  // Parse rows
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
 * Deterministic Markdown renderer for FinSight publication reports.
 * Formats headings, paragraphs, lists, financial tables, code snippets,
 * and converts [SOURCE N] into interactive CitationPills connected to the CitationDrawer.
 */
export function ReportViewer({
  content,
  citations = [],
  className,
}: ReportViewerProps) {
  if (!content) {
    return null;
  }

  const citationsList = citations || [];

  // Map source numbers to CitationResponse objects
  // The backend uses 1-based indexing in [SOURCE 1], [SOURCE 2]
  const resolveCitation = (sourceNum: number): CitationResponse | undefined => {
    const idx = sourceNum - 1;
    if (idx >= 0 && idx < citationsList.length) {
      return citationsList[idx];
    }
    return undefined;
  };

  /**
   * Helper to replace [SOURCE N] citations with interactive CitationPills
   * and parse inline formatting (bold, italics, inline code).
   */
  const renderInline = (text: string, keyPrefix: string): React.ReactNode => {
    const citationParts = text.split(/(\[SOURCE \d+\])/g);

    return citationParts.map((part, pIdx) => {
      const match = part.match(/\[SOURCE (\d+)\]/);
      if (match) {
        const sourceNum = match[1];
        const num = parseInt(sourceNum, 10);
        const matchingCitation = resolveCitation(num);

        return (
          <CitationPill
            key={`${keyPrefix}-cite-${pIdx}-${sourceNum}`}
            sourceNumber={sourceNum}
            chunkId={matchingCitation?.chunk_id}
            similarity={matchingCitation?.similarity}
            statementType={matchingCitation?.statement_type}
            fiscalPeriods={matchingCitation?.fiscal_periods}
          />
        );
      }

      // Handle simple inline markdown formatting: code, bold, italic
      return (
        <span key={`${keyPrefix}-txt-${pIdx}`}>
          {renderFormattedText(part, `${keyPrefix}-fmt-${pIdx}`)}
        </span>
      );
    });
  };

  const renderFormattedText = (raw: string, keyPrefix: string): React.ReactNode => {
    // Check for inline code `code`
    const codeParts = raw.split(/(`[^`]+`)/g);
    return codeParts.map((cPart, cIdx) => {
      if (cPart.startsWith("`") && cPart.endsWith("`") && cPart.length >= 2) {
        return (
          <code
            key={`${keyPrefix}-code-${cIdx}`}
            className="rounded bg-muted px-1.5 py-0.5 font-mono text-[12px] text-foreground font-semibold"
          >
            {cPart.slice(1, -1)}
          </code>
        );
      }

      // Check for bold **bold**
      const boldParts = cPart.split(/(\*\*[^*]+\*\*)/g);
      return boldParts.map((bPart, bIdx) => {
        if (bPart.startsWith("**") && bPart.endsWith("**") && bPart.length >= 4) {
          return (
            <strong
              key={`${keyPrefix}-bold-${cIdx}-${bIdx}`}
              className="font-semibold text-foreground"
            >
              {bPart.slice(2, -2)}
            </strong>
          );
        }

        // Check for italic *italic*
        const italicParts = bPart.split(/(\*[^*]+\*)/g);
        return italicParts.map((iPart, iIdx) => {
          if (iPart.startsWith("*") && iPart.endsWith("*") && iPart.length >= 2) {
            return (
              <em
                key={`${keyPrefix}-ital-${cIdx}-${bIdx}-${iIdx}`}
                className="italic text-muted-foreground"
              >
                {iPart.slice(1, -1)}
              </em>
            );
          }
          return iPart;
        });
      });
    });
  };

  // Split content into blocks (paragraphs, headings, tables, lists)
  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. Empty lines
    if (trimmed === "") {
      i++;
      continue;
    }

    // 2. Table Block (lines starting with | or containing |)
    if (trimmed.startsWith("|") && i + 1 < lines.length && lines[i + 1].trim().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }

      const tableMarkdown = tableLines.join("\n");
      const parsed = parseMarkdownTable(tableMarkdown);

      if (parsed) {
        blocks.push(
          <div
            key={`table-block-${i}`}
            className="my-4 rounded-lg border bg-card overflow-hidden shadow-2xs"
            data-testid="report-table"
          >
            <div className="overflow-x-auto max-h-[550px]">
              <Table className="w-full text-xs">
                <TableHeader className="bg-muted/50 sticky top-0 z-10 border-b">
                  <TableRow>
                    {parsed.headers.map((h, hIdx) => (
                      <TableHead
                        key={`th-${hIdx}`}
                        className={cn(
                          "text-xs font-semibold py-2.5 px-3.5 whitespace-nowrap text-foreground",
                          parsed.alignments[hIdx] === "right"
                            ? "text-right"
                            : parsed.alignments[hIdx] === "center"
                            ? "text-center"
                            : "text-left"
                        )}
                      >
                        {h}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {parsed.rows.map((row, rIdx) => (
                    <TableRow
                      key={`tr-${rIdx}`}
                      className="hover:bg-muted/30 transition-colors border-b last:border-b-0"
                    >
                      {parsed.headers.map((_, cIdx) => {
                        const cellVal = row[cIdx] || "";
                        const align = parsed.alignments[cIdx] || "left";
                        const isNegative =
                          /^\(.*\)$/.test(cellVal) || /^-\$?\d/.test(cellVal);

                        return (
                          <TableCell
                            key={`td-${rIdx}-${cIdx}`}
                            className={cn(
                              "py-2.5 px-3.5 whitespace-nowrap font-tabular-nums text-xs",
                              align === "right"
                                ? "text-right"
                                : align === "center"
                                ? "text-center"
                                : "text-left",
                              isNegative && "text-finance-negative font-medium"
                            )}
                          >
                            {renderInline(cellVal, `cell-${rIdx}-${cIdx}`)}
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
        continue;
      }
    }

    // 3. Headings
    if (trimmed.startsWith("# ")) {
      blocks.push(
        <h1
          key={`h1-${i}`}
          className="text-xl sm:text-2xl font-bold tracking-tight text-foreground mt-6 mb-3 pb-2 border-b"
        >
          {renderInline(trimmed.slice(2), `h1-${i}`)}
        </h1>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith("## ")) {
      blocks.push(
        <h2
          key={`h2-${i}`}
          className="text-base sm:text-lg font-semibold tracking-tight text-foreground mt-6 mb-2.5 flex items-center gap-2"
        >
          {renderInline(trimmed.slice(3), `h2-${i}`)}
        </h2>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith("### ")) {
      blocks.push(
        <h3
          key={`h3-${i}`}
          className="text-sm sm:text-base font-semibold text-foreground mt-4 mb-2"
        >
          {renderInline(trimmed.slice(4), `h3-${i}`)}
        </h3>
      );
      i++;
      continue;
    }

    // 4. Bullet list items
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const listItems: string[] = [];
      while (
        i < lines.length &&
        (lines[i].trim().startsWith("- ") || lines[i].trim().startsWith("* "))
      ) {
        listItems.push(lines[i].trim().slice(2));
        i++;
      }

      blocks.push(
        <ul
          key={`ul-${i}`}
          className="my-3 ml-5 list-disc space-y-1 text-sm text-foreground/90 leading-relaxed"
        >
          {listItems.map((item, lIdx) => (
            <li key={`li-${lIdx}`}>{renderInline(item, `li-${i}-${lIdx}`)}</li>
          ))}
        </ul>
      );
      continue;
    }

    // 5. Standard Paragraph
    blocks.push(
      <p
        key={`p-${i}`}
        className="my-2.5 text-sm text-foreground/90 leading-relaxed font-sans"
      >
        {renderInline(trimmed, `p-${i}`)}
      </p>
    );
    i++;
  }

  return (
    <div
      className={cn("report-content space-y-2 select-text", className)}
      data-testid="report-viewer"
    >
      {blocks}
    </div>
  );
}
