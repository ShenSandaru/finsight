import { http, HttpResponse } from "msw";
import {
  mockHealthResponse,
  mockDocumentList,
  mockDocument,
  mockDocumentUploadResponse,
  mockSearchResponse,
  mockRagResponse,
  mockSession,
  mockMessages,
  mockConversationQueryResponse,
  mockComparisonQueryResponse,
  mockReport,
  mockReportList,
  mockTextChunk,
  mockTableChunk,
  mockUser,
} from "./data";
import { ConversationMessageResponse } from "@/types/api";

export const sessionMessagesStore: Record<string, ConversationMessageResponse[]> = {};

export const handlers = [
  // Authentication
  http.get("*/api/v1/auth/me", () => {
    return HttpResponse.json(mockUser);
  }),

  http.post("*/api/v1/auth/logout", () => {
    return HttpResponse.json({ message: "Successfully logged out" });
  }),

  // Health
  http.get("*/health", () => {
    return HttpResponse.json(mockHealthResponse);
  }),

  // Documents
  http.get("*/api/v1/documents/", () => {
    return HttpResponse.json(mockDocumentList);
  }),

  http.get("*/api/v1/documents/chunks/:id", ({ params }) => {
    const { id } = params;
    if (id === "not-found" || id === "missing-chunk") {
      return HttpResponse.json(
        {
          error: {
            code: "NOT_FOUND",
            message: `Evidence chunk with ID '${id}' not found`,
            details: { chunk_id: id },
          },
        },
        { status: 404 }
      );
    }
    if (id === mockTableChunk.id) {
      return HttpResponse.json(mockTableChunk);
    }
    // Default to mockTextChunk or matching ID
    return HttpResponse.json({ ...mockTextChunk, id: String(id) });
  }),

  http.get("*/api/v1/documents/:id", ({ params }) => {
    const { id } = params;
    if (id === "not-found") {
      return HttpResponse.json(
        {
          error: {
            code: "NOT_FOUND",
            message: "Document not found",
            details: { document_id: id },
          },
        },
        { status: 404 }
      );
    }
    return HttpResponse.json({ ...mockDocument, id });
  }),

  http.post("*/api/v1/documents/upload", async () => {
    return HttpResponse.json(mockDocumentUploadResponse, { status: 201 });
  }),

  http.delete("*/api/v1/documents/:id", () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Search
  http.post("*/api/v1/search", async () => {
    return HttpResponse.json(mockSearchResponse);
  }),

  // RAG
  http.post("*/api/v1/rag/query", async () => {
    return HttpResponse.json(mockRagResponse);
  }),

  // Conversations
  http.post("*/api/v1/conversations", async ({ request }) => {
    let body: any = {};
    try {
      body = await request.json();
    } catch {
      // empty body
    }
    // If request specifies title like "New Research Inquiry" or empty, return newly initialized session
    // otherwise if it's the domain services test title "Apple FY2025 Margin Analysis", return mockSession
    if (body?.title === "Apple FY2025 Margin Analysis") {
      return HttpResponse.json(mockSession, { status: 201 });
    }

    const newSession = {
      ...mockSession,
      id: "new-session-" + Math.random().toString(36).substring(2, 9),
      title: body?.title || mockSession.title,
      message_count: 0,
    };
    return HttpResponse.json(newSession, { status: 201 });
  }),

  http.get("*/api/v1/conversations/:id", ({ params }) => {
    return HttpResponse.json({ ...mockSession, id: params.id });
  }),

  http.delete("*/api/v1/conversations/:id", ({ params }) => {
    return HttpResponse.json({
      message: "Session deleted successfully",
      session_id: String(params.id),
    });
  }),

  http.get("*/api/v1/conversations/:id/messages", ({ params }) => {
    const id = String(params.id);
    if (sessionMessagesStore[id]) {
      return HttpResponse.json(sessionMessagesStore[id]);
    }
    if (id === mockSession.id) {
      return HttpResponse.json(mockMessages);
    }
    return HttpResponse.json([]);
  }),

  http.post("*/api/v1/conversations/:id/query", async ({ request, params }) => {
    const id = String(params.id);
    let body: any = {};
    try {
      body = await request.json();
    } catch {
      // empty
    }
    const isComparison =
      body?.document_ids &&
      Array.isArray(body.document_ids) &&
      body.document_ids.length >= 2;

    const response = isComparison
      ? {
          ...mockComparisonQueryResponse,
          session_id: id,
        }
      : {
          ...mockConversationQueryResponse,
          session_id: id,
        };

    if (!sessionMessagesStore[id]) {
      sessionMessagesStore[id] = [];
    }
    sessionMessagesStore[id].push(
      {
        id: "user-" + Date.now(),
        session_id: id,
        role: "user",
        content: body?.query || "Query",
        created_at: new Date().toISOString(),
      },
      {
        id: "assistant-" + Date.now(),
        session_id: id,
        role: "assistant",
        content: response.answer,
        created_at: new Date().toISOString(),
        findings: response.findings,
      }
    );

    return HttpResponse.json(response);
  }),

  // Reports
  http.post("*/api/v1/reports", async () => {
    return HttpResponse.json({ ...mockReport, status: "pending" }, { status: 202 });
  }),

  http.get("*/api/v1/reports/:id", ({ params }) => {
    return HttpResponse.json({ ...mockReport, id: params.id });
  }),

  http.get("*/api/v1/reports", () => {
    return HttpResponse.json(mockReportList);
  }),

  http.delete("*/api/v1/reports/:id", () => {
    return new HttpResponse(null, { status: 204 });
  }),
];
