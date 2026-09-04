"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Clock, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import type { ReportStatus } from "@/types/api";

interface ReportStatusBadgeProps {
  status: ReportStatus | string;
  className?: string;
}

/**
 * Report Status Badge with distinct glyph, text label, and semantic styling
 * for all 4 backend lifecycle states: pending, processing, completed, failed.
 */
export function ReportStatusBadge({ status, className }: ReportStatusBadgeProps) {
  const normalized = (status || "").toLowerCase();

  switch (normalized) {
    case "completed":
      return (
        <Badge
          variant="outline"
          className={cn(
            "bg-finance-positive/10 text-finance-positive border-finance-positive/30 font-medium text-[11px] gap-1 px-2 py-0.5",
            className
          )}
          data-testid="report-status-completed"
        >
          <CheckCircle2 className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span>Completed</span>
        </Badge>
      );

    case "processing":
      return (
        <Badge
          variant="outline"
          className={cn(
            "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30 font-medium text-[11px] gap-1 px-2 py-0.5",
            className
          )}
          data-testid="report-status-processing"
        >
          <Loader2 className="h-3 w-3 shrink-0 animate-spin" aria-hidden="true" />
          <span>Processing</span>
        </Badge>
      );

    case "pending":
      return (
        <Badge
          variant="outline"
          className={cn(
            "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 font-medium text-[11px] gap-1 px-2 py-0.5",
            className
          )}
          data-testid="report-status-pending"
        >
          <Clock className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span>Pending</span>
        </Badge>
      );

    case "failed":
      return (
        <Badge
          variant="outline"
          className={cn(
            "bg-destructive/10 text-destructive border-destructive/30 font-medium text-[11px] gap-1 px-2 py-0.5",
            className
          )}
          data-testid="report-status-failed"
        >
          <AlertCircle className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span>Failed</span>
        </Badge>
      );

    default:
      return (
        <Badge
          variant="secondary"
          className={cn("text-[11px] capitalize", className)}
          data-testid="report-status-unknown"
        >
          {status}
        </Badge>
      );
  }
}
