import { apiClient } from "./client";
import type { RAGRequest, RAGResponseSchema } from "@/types/api";

/**
 * RAG & Grounded Financial Question Answering Domain API Service
 * 
 * Maps directly to backend/app/api/routes/rag.py
 */
export const ragApi = {
  /**
   * Execute single-turn grounded financial question answering with citations
   * POST /api/v1/rag/query
   */
  async query(
    request: RAGRequest,
    signal?: AbortSignal
  ): Promise<RAGResponseSchema> {
    return apiClient<RAGResponseSchema>("/api/v1/rag/query", {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    });
  },
};
