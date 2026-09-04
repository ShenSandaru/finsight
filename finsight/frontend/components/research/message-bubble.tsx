"use client";

import React from "react";
import { CitationPill } from "./citation-pill";
import { User, Bot } from "lucide-react";
import type { CitationResponse } from "@/types/api";

interface MessageBubbleProps {
  role: "user" | "assistant" | string;
  content: string;
  citations?: CitationResponse[];
  createdAt?: string;
}

export function MessageBubble({
  role,
  content,
  citations = [],
  createdAt,
}: MessageBubbleProps) {
  const isUser = role === "user";

  const renderContentWithCitations = (text: string) => {
    // Regex matching [SOURCE N] markers
    const parts = text.split(/(\[SOURCE \d+\])/g);

    return parts.map((part, index) => {
      const match = part.match(/\[SOURCE (\d+)\]/);
      if (match) {
        const sourceNum = match[1];
        // Match against citations list (0-indexed sourceNum - 1)
        const citationIndex = parseInt(sourceNum, 10) - 1;
        const matchingCitation = citations[citationIndex];

        return (
          <CitationPill
            key={`citation-${index}-${sourceNum}`}
            sourceNumber={sourceNum}
            chunkId={matchingCitation?.chunk_id}
          />
        );
      }
      return <span key={`text-${index}`}>{part}</span>;
    });
  };

  const formatTimestamp = (iso?: string) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div
      className={`flex gap-3 text-sm ${
        isUser ? "justify-end" : "justify-start"
      }`}
      data-testid={`message-bubble-${role}`}
    >
      {!isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary mt-0.5">
          <Bot className="h-4 w-4" aria-hidden="true" />
        </div>
      )}

      <div
        className={`flex flex-col space-y-1.5 max-w-[85%] sm:max-w-[75%] ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        <div
          className={`rounded-lg px-4 py-2.5 shadow-sm leading-relaxed whitespace-pre-wrap font-sans ${
            isUser
              ? "bg-primary text-primary-foreground font-medium"
              : "bg-card border text-card-foreground"
          }`}
        >
          {isUser ? content : renderContentWithCitations(content)}
        </div>

        {createdAt && (
          <span className="text-[10px] text-muted-foreground font-mono px-1">
            {formatTimestamp(createdAt)}
          </span>
        )}
      </div>

      {isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground mt-0.5">
          <User className="h-4 w-4" aria-hidden="true" />
        </div>
      )}
    </div>
  );
}
