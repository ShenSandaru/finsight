import React from "react";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, Clock, FileCheck, AlertCircle } from "lucide-react";
import type { DocumentStatus } from "@/types/api";

interface DocumentStatusBadgeProps {
  status: DocumentStatus | string;
  className?: string;
}

export function DocumentStatusBadge({ status, className }: DocumentStatusBadgeProps) {
  switch (status) {
    case "pending":
      return (
        <Badge
          variant="secondary"
          className={`gap-1.5 font-medium border-muted-foreground/20 text-muted-foreground ${className ?? ""}`}
          data-testid="status-badge-pending"
        >
          <Clock className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Queued</span>
        </Badge>
      );
    case "processing":
      return (
        <Badge
          variant="financeWarning"
          className={`gap-1.5 font-medium animate-pulse ${className ?? ""}`}
          data-testid="status-badge-processing"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          <span>Processing</span>
        </Badge>
      );
    case "parsed":
      return (
        <Badge
          variant="secondary"
          className={`gap-1.5 font-medium text-foreground bg-secondary/80 ${className ?? ""}`}
          data-testid="status-badge-parsed"
        >
          <FileCheck className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          <span>Parsed</span>
        </Badge>
      );
    case "indexed":
      return (
        <Badge
          variant="financePositive"
          className={`gap-1.5 font-medium ${className ?? ""}`}
          data-testid="status-badge-indexed"
        >
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Indexed</span>
        </Badge>
      );
    case "failed":
      return (
        <Badge
          variant="financeNegative"
          className={`gap-1.5 font-medium ${className ?? ""}`}
          data-testid="status-badge-failed"
        >
          <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Failed</span>
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className={className}>
          <span>{status}</span>
        </Badge>
      );
  }
}
