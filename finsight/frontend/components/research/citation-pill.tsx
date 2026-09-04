"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";

interface CitationPillProps {
  sourceNumber: string | number;
  chunkId?: string | null;
  similarity?: number | null;
  statementType?: string | null;
  fiscalPeriods?: string[] | null;
  className?: string;
}

export function CitationPill({
  sourceNumber,
  chunkId,
  similarity,
  statementType,
  fiscalPeriods,
  className,
}: CitationPillProps) {
  const openCitationDrawer = useUiStore((state) => state.openCitationDrawer);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (chunkId) {
      openCitationDrawer(chunkId, {
        sourceNumber,
        similarity,
        statementType,
        fiscalPeriods,
      });
    }
  };

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={handleClick}
      className={cn(
        "inline-flex items-center gap-1 h-5 px-1.5 py-0 text-[11px] font-mono font-medium rounded border-primary/20 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary/40 transition-colors align-baseline mx-0.5",
        className
      )}
      title={chunkId ? `View filing citation [SOURCE ${sourceNumber}]` : `Source citation ${sourceNumber}`}
      aria-label={`Source citation ${sourceNumber}`}
      data-testid={`citation-pill-${sourceNumber}`}
    >
      <FileText className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span>SOURCE {sourceNumber}</span>
    </Button>
  );
}
