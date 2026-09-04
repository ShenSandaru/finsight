"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { MessageSquareText, Plus, Sparkles } from "lucide-react";

interface ResearchEmptyStateProps {
  onCreateSession: () => void;
  isCreating: boolean;
  hasActiveSession: boolean;
}

export function ResearchEmptyState({
  onCreateSession,
  isCreating,
  hasActiveSession,
}: ResearchEmptyStateProps) {
  if (hasActiveSession) {
    return (
      <div
        className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-3"
        data-testid="empty-conversation-state"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-foreground">
            Start Your Financial Inquiry
          </h2>
          <p className="text-xs text-muted-foreground max-w-sm mx-auto">
            Ask targeted questions about corporate filings, revenue growth, margins, ratios, or cash flows. Responses will be grounded with verified citations.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-4"
      data-testid="no-sessions-empty-state"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <MessageSquareText className="h-6 w-6" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-foreground">
          No Active Research Session
        </h2>
        <p className="text-xs text-muted-foreground max-w-md mx-auto">
          Create an isolated research session to begin multi-turn conversational analysis across indexed 10-K and financial statements.
        </p>
      </div>
      <Button
        size="sm"
        onClick={onCreateSession}
        disabled={isCreating}
        className="gap-1.5 text-xs"
        data-testid="start-new-research-btn"
      >
        <Plus className="h-3.5 w-3.5" />
        <span>Start New Research</span>
      </Button>
    </div>
  );
}
