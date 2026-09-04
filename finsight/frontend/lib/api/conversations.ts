import { apiClient } from "./client";
import type {
  ConversationSessionResponse,
  ConversationMessageResponse,
  CreateSessionRequest,
  ConversationQueryRequest,
  ConversationQueryResponse,
  DeleteSessionResponse,
} from "@/types/api";

/**
 * Conversational Memory & Multi-Turn RAG Domain API Service
 * 
 * Maps directly to backend/app/api/routes/conversations.py
 */
export const conversationsApi = {
  /**
   * Create a new isolated conversation session
   * POST /api/v1/conversations
   */
  async createSession(
    request: CreateSessionRequest = {},
    signal?: AbortSignal
  ): Promise<ConversationSessionResponse> {
    return apiClient<ConversationSessionResponse>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    });
  },

  /**
   * Get metadata and message count for a specific session
   * GET /api/v1/conversations/{session_id}
   */
  async getSession(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<ConversationSessionResponse> {
    return apiClient<ConversationSessionResponse>(
      `/api/v1/conversations/${sessionId}`,
      {
        signal,
      }
    );
  },

  /**
   * Delete a session and cascade delete its message history
   * DELETE /api/v1/conversations/{session_id}
   */
  async deleteSession(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<DeleteSessionResponse> {
    return apiClient<DeleteSessionResponse>(
      `/api/v1/conversations/${sessionId}`,
      {
        method: "DELETE",
        signal,
      }
    );
  },

  /**
   * Get chronological message history for a session
   * GET /api/v1/conversations/{session_id}/messages
   */
  async getMessages(
    sessionId: string,
    limit = 50,
    signal?: AbortSignal
  ): Promise<ConversationMessageResponse[]> {
    return apiClient<ConversationMessageResponse[]>(
      `/api/v1/conversations/${sessionId}/messages`,
      {
        params: { limit },
        signal,
      }
    );
  },

  /**
   * Ask a multi-turn grounded financial question in a session
   * POST /api/v1/conversations/{session_id}/query
   */
  async querySession(
    sessionId: string,
    request: ConversationQueryRequest,
    signal?: AbortSignal
  ): Promise<ConversationQueryResponse> {
    return apiClient<ConversationQueryResponse>(
      `/api/v1/conversations/${sessionId}/query`,
      {
        method: "POST",
        body: JSON.stringify(request),
        signal,
      }
    );
  },
};
