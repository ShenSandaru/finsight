import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CitationPill } from "@/components/research/citation-pill";
import { MessageBubble } from "@/components/research/message-bubble";
import { ResearchInput } from "@/components/research/research-input";
import { SelectedDocumentContext } from "@/components/research/selected-document-context";
import { ConversationSidebar } from "@/components/research/conversation-sidebar";
import { MessageThread } from "@/components/research/message-thread";
import ResearchPage from "@/app/research/page";
import { useUiStore } from "@/stores/ui-store";
import {
  mockSession,
  mockMessages,
  mockConversationQueryResponse,
  mockDocument,
} from "./mocks/data";
import { server } from "./mocks/server";
import { http, HttpResponse } from "msw";

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("Phase 11.4 Research Chat Workspace UI Test Suite", () => {
  beforeEach(() => {
    useUiStore.setState({
      selectedDocumentIds: [],
      sidebarOpen: true,
      citationDrawerOpen: false,
      activeCitationChunkId: null,
    });
  });

  // ============================================================
  // 1. Citation Pill & Marker Parsing
  // ============================================================
  describe("CitationPill & MessageBubble Citation Parsing", () => {
    it("renders CitationPill with source number and triggers drawer store action", () => {
      render(
        <CitationPill sourceNumber="1" chunkId="chunk-123" />
      );

      const pill = screen.getByTestId("citation-pill-1");
      expect(pill).toBeInTheDocument();
      expect(screen.getByText("SOURCE 1")).toBeInTheDocument();

      fireEvent.click(pill);
      expect(useUiStore.getState().citationDrawerOpen).toBe(true);
      expect(useUiStore.getState().activeCitationChunkId).toBe("chunk-123");
    });

    it("parses [SOURCE N] markers inside assistant message into CitationPills", () => {
      const citations = [
        {
          chunk_id: "chunk-apple-1",
          document_id: "doc-apple-1",
          page_number: 14,
          chunk_type: "table",
          similarity: 0.94,
          statement_type: "income_statement",
          fiscal_periods: ["2025"],
        },
      ];

      render(
        <MessageBubble
          role="assistant"
          content="Total revenue in FY2025 was $391,035M [SOURCE 1] with positive operating growth."
          citations={citations}
        />
      );

      expect(screen.getByTestId("message-bubble-assistant")).toBeInTheDocument();
      expect(screen.getByTestId("citation-pill-1")).toBeInTheDocument();
      expect(screen.getByText(/Total revenue in FY2025 was \$391,035M/)).toBeInTheDocument();
    });

    it("renders user message bubble distinctly", () => {
      render(
        <MessageBubble
          role="user"
          content="Compare Apple Q4 revenue and gross margin"
          createdAt="2026-08-24T10:10:05Z"
        />
      );

      const userBubble = screen.getByTestId("message-bubble-user");
      expect(userBubble).toBeInTheDocument();
      expect(screen.getByText("Compare Apple Q4 revenue and gross margin")).toBeInTheDocument();
    });
  });

  // ============================================================
  // 2. Selected Document Context
  // ============================================================
  describe("SelectedDocumentContext", () => {
    it("renders default context state when zero documents are selected", () => {
      const Wrapper = createTestWrapper();
      render(<SelectedDocumentContext />, { wrapper: Wrapper });

      expect(screen.getByTestId("selected-document-context-empty")).toBeInTheDocument();
      expect(screen.getByText(/all repository filings/i)).toBeInTheDocument();
    });

    it("renders selected filing badges and clears selection on action", async () => {
      useUiStore.setState({ selectedDocumentIds: [mockDocument.id] });
      const Wrapper = createTestWrapper();

      render(<SelectedDocumentContext />, { wrapper: Wrapper });

      expect(screen.getByTestId("selected-document-context")).toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getByText(mockDocument.title!)).toBeInTheDocument();
      });

      const clearBtn = screen.getByTestId("clear-context-docs-btn");
      fireEvent.click(clearBtn);

      expect(useUiStore.getState().selectedDocumentIds).toEqual([]);
    });
  });

  // ============================================================
  // 3. Research Input
  // ============================================================
  describe("ResearchInput", () => {
    it("submits question on form submit or Enter key press", () => {
      let submittedQuery = "";
      render(
        <ResearchInput
          query="What was Apple FCF in 2025?"
          onQueryChange={() => {}}
          onSubmit={(q) => {
            submittedQuery = q;
          }}
          isSubmitting={false}
        />
      );

      const submitBtn = screen.getByTestId("submit-query-btn");
      expect(submitBtn).not.toBeDisabled();

      fireEvent.click(submitBtn);
      expect(submittedQuery).toBe("What was Apple FCF in 2025?");
    });

    it("disables submit button on whitespace query or during submission", () => {
      render(
        <ResearchInput
          query="   "
          onQueryChange={() => {}}
          onSubmit={() => {}}
          isSubmitting={false}
        />
      );

      const submitBtn = screen.getByTestId("submit-query-btn");
      expect(submitBtn).toBeDisabled();
    });
  });

  // ============================================================
  // 4. Conversation Sidebar & Deletion
  // ============================================================
  describe("ConversationSidebar", () => {
    it("renders session list and handles session selection", () => {
      let selectedId = "";
      render(
        <ConversationSidebar
          conversations={[mockSession]}
          activeSessionId={null}
          onSelectSession={(id) => {
            selectedId = id;
          }}
          onCreateSession={() => {}}
          onDeleteSession={() => {}}
          isCreating={false}
          isDeleting={false}
        />
      );

      expect(screen.getByText(mockSession.title!)).toBeInTheDocument();

      const sessionItem = screen.getByTestId(`session-item-${mockSession.id}`);
      fireEvent.click(sessionItem);

      expect(selectedId).toBe(mockSession.id);
    });

    it("opens delete confirmation dialog and triggers deletion callback", () => {
      let deletedId = "";
      render(
        <ConversationSidebar
          conversations={[mockSession]}
          activeSessionId={mockSession.id}
          onSelectSession={() => {}}
          onCreateSession={() => {}}
          onDeleteSession={(id) => {
            deletedId = id;
          }}
          isCreating={false}
          isDeleting={false}
        />
      );

      const deleteBtn = screen.getByTestId(`delete-session-btn-${mockSession.id}`);
      fireEvent.click(deleteBtn);

      expect(screen.getByTestId("delete-session-dialog")).toBeInTheDocument();

      const confirmBtn = screen.getByTestId("confirm-delete-session-btn");
      fireEvent.click(confirmBtn);

      expect(deletedId).toBe(mockSession.id);
    });
  });

  // ============================================================
  // 5. Full ResearchPage Workspace Integration
  // ============================================================
  describe("ResearchPage Workspace", () => {
    it("renders empty research state when no sessions are open", () => {
      const Wrapper = createTestWrapper();
      render(<ResearchPage />, { wrapper: Wrapper });

      expect(screen.getByTestId("research-workspace-page")).toBeInTheDocument();
      expect(screen.getByTestId("no-sessions-empty-state")).toBeInTheDocument();
      expect(screen.getByTestId("start-new-research-btn")).toBeInTheDocument();
    });

    it("creates a new session and renders empty conversation prompt", async () => {
      const Wrapper = createTestWrapper();
      render(<ResearchPage />, { wrapper: Wrapper });

      const newBtn = screen.getByTestId("start-new-research-btn");
      fireEvent.click(newBtn);

      await waitFor(() => {
        expect(screen.getByTestId("empty-conversation-state")).toBeInTheDocument();
      });
      expect(screen.getByText("Start Your Financial Inquiry")).toBeInTheDocument();
    });

    it("submits research question, displays loading state, and renders grounded answer with citations", async () => {
      const Wrapper = createTestWrapper();
      render(<ResearchPage />, { wrapper: Wrapper });

      // Create session first
      const newBtn = screen.getByTestId("start-new-research-btn");
      fireEvent.click(newBtn);

      await waitFor(() => {
        expect(screen.getByTestId("empty-conversation-state")).toBeInTheDocument();
      });

      // Submit query
      const textarea = screen.getByTestId("research-query-textarea");
      fireEvent.change(textarea, { target: { value: "What was Apple's gross margin in 2025?" } });

      const submitBtn = screen.getByTestId("submit-query-btn");
      fireEvent.click(submitBtn);

      // Verify grounded response and citation rendering
      await waitFor(() => {
        expect(
          screen.getByText(/Apple's gross margin for FY2025 was 46\.23%/)
        ).toBeInTheDocument();
        expect(screen.getByTestId("citation-pill-1")).toBeInTheDocument();
      });
    });

    it("handles research query API error gracefully", async () => {
      server.use(
        http.post("*/api/v1/conversations/:id/query", () => {
          return HttpResponse.json(
            {
              error: {
                code: "EXTERNAL_SERVICE_ERROR",
                message: "Gemini 2.0 Flash service rate limit exceeded.",
              },
            },
            { status: 502 }
          );
        })
      );

      const Wrapper = createTestWrapper();
      render(<ResearchPage />, { wrapper: Wrapper });

      // Create session
      const newBtn = screen.getByTestId("start-new-research-btn");
      fireEvent.click(newBtn);

      await waitFor(() => {
        expect(screen.getByTestId("empty-conversation-state")).toBeInTheDocument();
      });

      // Submit question
      const textarea = screen.getByTestId("research-query-textarea");
      fireEvent.change(textarea, { target: { value: "Trigger error query" } });

      const submitBtn = screen.getByTestId("submit-query-btn");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByTestId("research-error-bar")).toBeInTheDocument();
      });
      expect(
        screen.getByText(/rate limit exceeded/i)
      ).toBeInTheDocument();
    });
  });
});
