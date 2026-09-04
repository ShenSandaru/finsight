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
  mockReport,
  mockReportList,
} from "./data";

export const handlers = [
  // Health
  http.get("*/health", () => {
    return HttpResponse.json(mockHealthResponse);
  }),

  // Documents
  http.get("*/api/v1/documents/", () => {
    return HttpResponse.json(mockDocumentList);
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
  http.post("*/api/v1/conversations", async () => {
    return HttpResponse.json(mockSession, { status: 201 });
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

  http.get("*/api/v1/conversations/:id/messages", () => {
    return HttpResponse.json(mockMessages);
  }),

  http.post("*/api/v1/conversations/:id/query", async () => {
    return HttpResponse.json(mockConversationQueryResponse);
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
