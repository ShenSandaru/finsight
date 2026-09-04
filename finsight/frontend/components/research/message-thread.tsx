"use client";

import React, { useEffect, useRef } from "react";
import { MessageBubble } from "./message-bubble";
import { Loader2 } from "lucide-react";
import type { ConversationMessageResponse, CitationResponse } from "@/types/api";

interface MessageThreadProps {
  messages: ConversationMessageResponse[];
  isQuerying: boolean;
  activeCitations?: CitationResponse[];
  optimisticUserQuery?: string | null;
}

export function MessageThread({
  messages,
  isQuerying,
  activeCitations = [],
  optimisticUserQuery = null,
}: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages or query state changes
  useEffect(() => {
    if (typeof bottomRef.current?.scrollIntoView === "function") {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, isQuerying, optimisticUserQuery]);

  return (
    <div
      className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4"
      data-testid="message-thread"
    >
      {messages.map((msg, index) => {
        // Associate citations with assistant messages (e.g. latest response)
        const isLatestAssistant =
          msg.role === "assistant" && index === messages.length - 1;
        const citations = isLatestAssistant ? activeCitations : [];

        return (
          <MessageBubble
            key={msg.id || `msg-${index}`}
            role={msg.role}
            content={msg.content}
            citations={citations}
            createdAt={msg.created_at}
          />
        );
      })}

      {/* Optimistic user query rendering while research is in progress */}
      {optimisticUserQuery && (
        <MessageBubble
          role="user"
          content={optimisticUserQuery}
          createdAt={new Date().toISOString()}
        />
      )}

      {/* In-progress research state indicator */}
      {isQuerying && (
        <div
          className="flex items-center gap-3 p-3 rounded-lg border bg-muted/20 text-muted-foreground text-xs animate-pulse max-w-md"
          role="status"
          data-testid="research-loading-state"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          </div>
          <div className="space-y-0.5">
            <p className="font-medium text-foreground">
              Synthesizing financial evidence...
            </p>
            <p className="text-[11px] text-muted-foreground">
              Executing LangGraph multi-agent research & deterministic guardrails audit
            </p>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
