import { apiClient } from "./client";
import type { SearchRequest, SearchResponse } from "@/types/api";

/**
 * Search & Vector Retrieval Domain API Service
 * 
 * Maps directly to backend/app/api/routes/search.py
 */
export const searchApi = {
  /**
   * Search indexed chunks using semantic vector similarity without LLM answer generation
   * POST /api/v1/search
   */
  async search(
    request: SearchRequest,
    signal?: AbortSignal
  ): Promise<SearchResponse> {
    return apiClient<SearchResponse>("/api/v1/search", {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    });
  },
};
