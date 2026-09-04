import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  useDocuments,
  useDocument,
  useUploadDocument,
  useDeleteDocument,
} from "@/hooks/use-documents";
import { useSearch, useSearchMutation } from "@/hooks/use-search";
import { useRagQuery } from "@/hooks/use-rag";
import {
  useConversationSession,
  useConversationMessages,
  useCreateSession,
  useDeleteSession,
  useConversationQuery,
} from "@/hooks/use-conversations";
import {
  useReports,
  useReport,
  useCreateReport,
  useDeleteReport,
} from "@/hooks/use-reports";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("TanStack Query Hooks Test Suite", () => {
  describe("useDocuments & Document Mutations", () => {
    it("fetches document list successfully", async () => {
      const { result } = renderHook(() => useDocuments(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        if (result.current.isError) {
          console.error("Hook error:", result.current.error);
        }
        expect(result.current.isSuccess).toBe(true);
      });
      expect(result.current.data?.total).toBe(2);
      expect(result.current.data?.documents[0].filename).toBe("apple_10k_2025.pdf");
    });

    it("fetches single document detail", async () => {
      const { result } = renderHook(
        () => useDocument("11111111-1111-1111-1111-111111111111"),
        { wrapper: createWrapper() }
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.id).toBe("11111111-1111-1111-1111-111111111111");
    });

    it("uploads document via useUploadDocument mutation", async () => {
      const { result } = renderHook(() => useUploadDocument(), {
        wrapper: createWrapper(),
      });

      const file = new File(["dummy"], "test.pdf", { type: "application/pdf" });
      result.current.mutate({ file, title: "Test Doc" });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.document.status).toBe("processing");
    });

    it("deletes document via useDeleteDocument mutation", async () => {
      const { result } = renderHook(() => useDeleteDocument(), {
        wrapper: createWrapper(),
      });

      result.current.mutate("11111111-1111-1111-1111-111111111111");
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toBeNull();
    });
  });

  describe("useSearch & useSearchMutation", () => {
    it("executes semantic search query hook", async () => {
      const { result } = renderHook(
        () => useSearch({ query: "revenue 2025" }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.total_results).toBe(1);
    });

    it("executes on-demand search mutation", async () => {
      const { result } = renderHook(() => useSearchMutation(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ query: "operating margin" });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.results.length).toBe(1);
    });
  });

  describe("useRagQuery", () => {
    it("submits single-turn RAG query", async () => {
      const { result } = renderHook(() => useRagQuery(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ query: "Apple revenue 2025" });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.grounded).toBe(true);
      expect(result.current.data?.citations.length).toBe(1);
    });
  });

  describe("useConversations Hooks & Mutations", () => {
    it("fetches session and message history", async () => {
      const { result: sessionResult } = renderHook(
        () => useConversationSession("44444444-4444-4444-4444-444444444444"),
        { wrapper: createWrapper() }
      );
      await waitFor(() => expect(sessionResult.current.isSuccess).toBe(true));
      expect(sessionResult.current.data?.title).toBe("Apple FY2025 Margin Analysis");

      const { result: msgResult } = renderHook(
        () => useConversationMessages("44444444-4444-4444-4444-444444444444"),
        { wrapper: createWrapper() }
      );
      await waitFor(() => expect(msgResult.current.isSuccess).toBe(true));
      expect(msgResult.current.data?.length).toBe(2);
    });

    it("creates a session and submits a query", async () => {
      const { result: createResult } = renderHook(() => useCreateSession(), {
        wrapper: createWrapper(),
      });
      createResult.current.mutate({ title: "New Session" });
      await waitFor(() => expect(createResult.current.isSuccess).toBe(true));

      const { result: queryResult } = renderHook(
        () => useConversationQuery("44444444-4444-4444-4444-444444444444"),
        { wrapper: createWrapper() }
      );
      queryResult.current.mutate({ query: "What was gross margin?" });
      await waitFor(() => expect(queryResult.current.isSuccess).toBe(true));
      expect(queryResult.current.data?.grounded).toBe(true);
    });

    it("deletes a session", async () => {
      const { result } = renderHook(() => useDeleteSession(), {
        wrapper: createWrapper(),
      });
      result.current.mutate("44444444-4444-4444-4444-444444444444");
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.session_id).toBe("44444444-4444-4444-4444-444444444444");
    });
  });

  describe("useReports Hooks & Mutations", () => {
    it("lists reports and fetches report detail", async () => {
      const { result: listResult } = renderHook(() => useReports(), {
        wrapper: createWrapper(),
      });
      await waitFor(() => expect(listResult.current.isSuccess).toBe(true));
      expect(listResult.current.data?.total).toBe(1);

      const { result: detailResult } = renderHook(
        () => useReport("66666666-6666-6666-6666-666666666666"),
        { wrapper: createWrapper() }
      );
      await waitFor(() => expect(detailResult.current.isSuccess).toBe(true));
      expect(detailResult.current.data?.status).toBe("completed");
    });

    it("creates and deletes a research report", async () => {
      const { result: createResult } = renderHook(() => useCreateReport(), {
        wrapper: createWrapper(),
      });
      createResult.current.mutate({ query: "Report query" });
      await waitFor(() => expect(createResult.current.isSuccess).toBe(true));
      expect(createResult.current.data?.status).toBe("pending");

      const { result: deleteResult } = renderHook(() => useDeleteReport(), {
        wrapper: createWrapper(),
      });
      deleteResult.current.mutate("66666666-6666-6666-6666-666666666666");
      await waitFor(() => expect(deleteResult.current.isSuccess).toBe(true));
      expect(deleteResult.current.data).toBeNull();
    });
  });
});
