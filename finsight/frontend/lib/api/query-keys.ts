import type { SearchRequest, ListReportsParams } from "@/types/api";

/**
 * Centralized TanStack Query Key Factory
 * 
 * Ensures consistent cache key generation and deterministic invalidation across hooks.
 */
export const queryKeys = {
  // Health
  health: () => ["health"] as const,

  // Documents
  documents: {
    all: () => ["documents"] as const,
    list: () => ["documents", "list"] as const,
    detail: (id: string) => ["documents", "detail", id] as const,
  },

  // Search
  search: (params: SearchRequest) => ["search", params] as const,

  // Conversations
  conversations: {
    all: () => ["conversations"] as const,
    detail: (sessionId: string) => ["conversations", "detail", sessionId] as const,
    messages: (sessionId: string, limit = 50) =>
      ["conversations", "messages", sessionId, { limit }] as const,
  },

  // Reports
  reports: {
    all: () => ["reports"] as const,
    list: (params: ListReportsParams = {}) => ["reports", "list", params] as const,
    detail: (reportId: string) => ["reports", "detail", reportId] as const,
  },
};
