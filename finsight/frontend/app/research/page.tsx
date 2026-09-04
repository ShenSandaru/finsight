"use client";

import React, { useState, useEffect } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { ConversationSidebar } from "@/components/research/conversation-sidebar";
import { MessageThread } from "@/components/research/message-thread";
import { ResearchInput } from "@/components/research/research-input";
import { SelectedDocumentContext } from "@/components/research/selected-document-context";
import { ResearchEmptyState } from "@/components/research/research-empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/api/query-keys";
import {
  useCreateSession,
  useDeleteSession,
  useConversationMessages,
  useConversationQuery,
  useConversationSession,
} from "@/hooks/use-conversations";
import { useUiStore } from "@/stores/ui-store";
import { CitationDrawer } from "@/components/citations/citation-drawer";
import type {
  ConversationSessionResponse,
  CitationResponse,
  ConversationMessageResponse,
  FinancialFinding,
} from "@/types/api";

export default function ResearchPage() {
  const queryClient = useQueryClient();
  const [sessions, setSessions] = useState<ConversationSessionResponse[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [queryInput, setQueryInput] = useState("");
  const [optimisticUserQuery, setOptimisticUserQuery] = useState<string | null>(null);
  const [activeCitations, setActiveCitations] = useState<CitationResponse[]>([]);
  const [activeFindings, setActiveFindings] = useState<FinancialFinding[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedDocumentIds = useUiStore((state) => state.selectedDocumentIds);

  const { mutate: createSession, isPending: isCreating } = useCreateSession();
  const { mutate: deleteSession, isPending: isDeleting } = useDeleteSession();

  // Active Session Metadata
  const {
    data: sessionData,
    isLoading: isSessionLoading,
  } = useConversationSession(activeSessionId || "");

  // Update session metadata in local list when fetched
  useEffect(() => {
    if (sessionData) {
      setSessions((prev) => {
        const index = prev.findIndex((s) => s.id === sessionData.id);
        if (index >= 0) {
          const updated = [...prev];
          updated[index] = sessionData;
          return updated;
        }
        return [sessionData, ...prev];
      });
    }
  }, [sessionData]);

  // Messages Query for the active session
  const {
    data: messagesData,
    isLoading: isMessagesLoading,
    isError: isMessagesError,
    error: messagesError,
  } = useConversationMessages(activeSessionId || "", 50);

  const messages = messagesData || [];

  // Query Mutation for the active session
  const {
    mutate: executeQuery,
    isPending: isQuerying,
  } = useConversationQuery(activeSessionId || "");

  // Handle new research session creation
  const handleCreateSession = (title?: string) => {
    setErrorMessage(null);
    createSession(
      { title: title || "New Research Inquiry" },
      {
        onSuccess: (newSession) => {
          setSessions((prev) => [newSession, ...prev]);
          setActiveSessionId(newSession.id);
          setActiveCitations([]);
          setActiveFindings([]);
        },
        onError: (err) => {
          setErrorMessage(err.message || "Failed to initialize research session.");
        },
      }
    );
  };

  // Handle session deletion
  const handleDeleteSession = (sessionId: string) => {
    setErrorMessage(null);
    deleteSession(sessionId, {
      onSuccess: () => {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (activeSessionId === sessionId) {
          const remaining = sessions.filter((s) => s.id !== sessionId);
          setActiveSessionId(remaining.length > 0 ? remaining[0].id : null);
          setActiveCitations([]);
        }
      },
      onError: (err) => {
        setErrorMessage(err.message || "Failed to delete research session.");
      },
    });
  };

  // Handle query submission
  const handleSubmitQuery = (submittedQuery: string) => {
    if (!activeSessionId) {
      // Auto-create session if none active
      createSession(
        { title: submittedQuery.slice(0, 40) + "..." },
        {
          onSuccess: (newSession) => {
            setSessions((prev) => [newSession, ...prev]);
            setActiveSessionId(newSession.id);
            dispatchQuery(newSession.id, submittedQuery);
          },
          onError: (err) => {
            setErrorMessage(err.message || "Failed to initialize research session.");
          },
        }
      );
      return;
    }

    dispatchQuery(activeSessionId, submittedQuery);
  };

  const dispatchQuery = (sessionId: string, text: string) => {
    setErrorMessage(null);
    setOptimisticUserQuery(text);
    setQueryInput("");

    executeQuery(
      {
        query: text,
        document_ids: selectedDocumentIds.length > 0 ? selectedDocumentIds : undefined,
      },
      {
        onSuccess: (res) => {
          setOptimisticUserQuery(null);
          setActiveCitations(res.citations || []);
          setActiveFindings(res.findings || []);

          // Immediately append user and assistant messages into cache
          queryClient.setQueryData<ConversationMessageResponse[]>(
            queryKeys.conversations.messages(sessionId, 50),
            (old = []) => [
              ...old,
              {
                id: "user-" + Date.now(),
                session_id: sessionId,
                role: "user",
                content: text,
                created_at: new Date().toISOString(),
              },
              {
                id: "assistant-" + Date.now(),
                session_id: sessionId,
                role: "assistant",
                content: res.answer,
                findings: res.findings || [],
                created_at: new Date().toISOString(),
              },
            ]
          );
        },
        onError: (err) => {
          setOptimisticUserQuery(null);
          setErrorMessage(err.message || "Failed to process research inquiry.");
        },
      }
    );
  };

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <AppShell>
      <div
        className="h-[calc(100vh-4rem)] flex flex-col sm:flex-row rounded-lg border bg-card overflow-hidden shadow-sm"
        data-testid="research-workspace-page"
      >
        {/* Left: Conversation Navigation Sidebar */}
        <ConversationSidebar
          conversations={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={(id) => {
            setActiveSessionId(id);
            setActiveCitations([]);
            setErrorMessage(null);
          }}
          onCreateSession={() => handleCreateSession()}
          onDeleteSession={handleDeleteSession}
          isCreating={isCreating}
          isDeleting={isDeleting}
        />

        {/* Right: Message Stream & Inquiry Workspace */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-background">
          {/* Active Workspace Header */}
          <div className="flex items-center justify-between border-b px-4 py-3 bg-card shrink-0">
            <div>
              <h1 className="text-sm font-semibold text-foreground">
                {activeSession?.title || "Financial Research Workspace"}
              </h1>
              <p className="text-[11px] text-muted-foreground">
                Grounded multi-agent conversational RAG with LangGraph & citation auditing
              </p>
            </div>
          </div>

          {/* Error Notification Bar */}
          {errorMessage && (
            <div
              className="flex items-center gap-2 border-b border-destructive/20 bg-destructive/10 px-4 py-2 text-xs text-destructive shrink-0"
              role="alert"
              data-testid="research-error-bar"
            >
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Main Thread Content */}
          {!activeSessionId ? (
            <ResearchEmptyState
              hasActiveSession={false}
              onCreateSession={() => handleCreateSession()}
              isCreating={isCreating}
            />
          ) : isMessagesLoading && messages.length === 0 ? (
            <div
              className="flex-1 p-6 space-y-4"
              data-testid="research-messages-loading"
            >
              <Skeleton className="h-10 w-2/3 ml-auto rounded-lg" />
              <Skeleton className="h-24 w-3/4 rounded-lg" />
              <Skeleton className="h-10 w-1/2 ml-auto rounded-lg" />
            </div>
          ) : isMessagesError ? (
            <div
              className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-2"
              data-testid="research-messages-error"
            >
              <AlertCircle className="h-6 w-6 text-destructive" />
              <p className="text-xs text-muted-foreground">
                {messagesError?.message || "Failed to load session messages."}
              </p>
            </div>
          ) : messages.length === 0 && !optimisticUserQuery ? (
            <ResearchEmptyState
              hasActiveSession={true}
              onCreateSession={() => {}}
              isCreating={false}
            />
          ) : (
            <MessageThread
              messages={messages}
              isQuerying={isQuerying}
              activeCitations={activeCitations}
              activeFindings={activeFindings}
              optimisticUserQuery={optimisticUserQuery}
            />
          )}

          {/* Footer: Scoped Context & Query Input */}
          <div className="p-3 sm:p-4 border-t bg-card space-y-2 shrink-0">
            <SelectedDocumentContext />
            <ResearchInput
              query={queryInput}
              onQueryChange={setQueryInput}
              onSubmit={handleSubmitQuery}
              isSubmitting={isQuerying}
              disabled={isCreating}
            />
          </div>
        </div>
      </div>

      {/* Citation & Evidence Inspector Drawer (Phase 11.5) */}
      <CitationDrawer />
    </AppShell>
  );
}
