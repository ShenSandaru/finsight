"use client";

import React, { useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ArrowUp, Loader2 } from "lucide-react";

interface ResearchInputProps {
  query: string;
  onQueryChange: (query: string) => void;
  onSubmit: (query: string) => void;
  isSubmitting: boolean;
  placeholder?: string;
  disabled?: boolean;
}

export function ResearchInput({
  query,
  onQueryChange,
  onSubmit,
  isSubmitting,
  placeholder = "Ask about revenue, operating margins, balance sheet items, CAGR, or trends...",
  disabled = false,
}: ResearchInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height up to 160px
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        160
      )}px`;
    }
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleFormSubmit();
    }
  };

  const handleFormSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isSubmitting || disabled) return;
    onSubmit(trimmed);
  };

  const isBlank = !query.trim();

  return (
    <form
      onSubmit={handleFormSubmit}
      className="relative rounded-lg border bg-card shadow-sm transition-all focus-within:border-primary focus-within:ring-1 focus-within:ring-primary"
      data-testid="research-input-form"
    >
      <Textarea
        ref={textareaRef}
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isSubmitting || disabled}
        rows={2}
        className="resize-none border-0 bg-transparent px-3 py-2.5 text-sm shadow-none focus-visible:ring-0 focus-visible:outline-none pr-12 min-h-[56px] max-h-[160px]"
        aria-label="Financial research query input"
        data-testid="research-query-textarea"
      />

      <div className="flex items-center justify-between border-t border-border/40 px-3 py-1.5 bg-muted/10">
        <span className="text-[11px] text-muted-foreground">
          Press <kbd className="font-mono text-[10px] bg-muted px-1 py-0.5 rounded">Enter</kbd> to submit,{" "}
          <kbd className="font-mono text-[10px] bg-muted px-1 py-0.5 rounded">Shift+Enter</kbd> for newline
        </span>

        <Button
          type="submit"
          size="icon"
          disabled={isBlank || isSubmitting || disabled}
          className="h-7 w-7 rounded-md shrink-0 transition-opacity"
          aria-label="Submit financial query"
          data-testid="submit-query-btn"
        >
          {isSubmitting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <ArrowUp className="h-4 w-4" aria-hidden="true" />
          )}
        </Button>
      </div>
    </form>
  );
}
