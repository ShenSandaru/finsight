import { useMutation } from "@tanstack/react-query";
import { ragApi } from "@/lib/api/rag";
import type { RAGRequest, RAGResponseSchema } from "@/types/api";

/**
 * Mutation hook for single-turn grounded financial question answering
 */
export function useRagQuery() {
  return useMutation<RAGResponseSchema, Error, RAGRequest>({
    mutationFn: (request) => ragApi.query(request),
  });
}
