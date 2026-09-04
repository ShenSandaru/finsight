import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { documentsApi } from "@/lib/api/documents";
import { queryKeys } from "@/lib/api/query-keys";
import type {
  DocumentResponse,
  DocumentListResponse,
  DocumentUploadParams,
  DocumentUploadResponse,
  DocumentChunkResponse,
} from "@/types/api";

/**
 * Hook to list all documents with smart background polling if any document is processing
 */
export function useDocuments(
  options?: Partial<UseQueryOptions<DocumentListResponse, Error>>
) {
  return useQuery({
    queryKey: queryKeys.documents.list(),
    queryFn: ({ signal }) => documentsApi.list(signal),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      // Auto-poll every 2.5s if any document is still in 'pending' or 'processing'
      const hasActive = data.documents.some(
        (doc) => doc.status === "pending" || doc.status === "processing"
      );
      return hasActive ? 2500 : false;
    },
    ...options,
  });
}

/**
 * Hook to get a single document with polling until terminal status is reached
 */
export function useDocument(
  documentId: string,
  options?: Partial<UseQueryOptions<DocumentResponse, Error>>
) {
  return useQuery({
    queryKey: queryKeys.documents.detail(documentId),
    queryFn: ({ signal }) => documentsApi.get(documentId, signal),
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const doc = query.state.data;
      if (!doc) return false;
      // Continue polling if pending or processing
      if (doc.status === "pending" || doc.status === "processing") {
        return 2000;
      }
      return false;
    },
    ...options,
  });
}

/**
 * Mutation hook to upload a document
 */
export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation<DocumentUploadResponse, Error, DocumentUploadParams>({
    mutationFn: (params) => documentsApi.upload(params),
    onSuccess: () => {
      // Invalidate documents list to refresh state
      queryClient.invalidateQueries({ queryKey: queryKeys.documents.all() });
    },
  });
}

/**
 * Mutation hook to delete a document
 */
export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation<null, Error, string>({
    mutationFn: (documentId) => documentsApi.delete(documentId),
    onSuccess: (_, documentId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.documents.all() });
      queryClient.removeQueries({
        queryKey: queryKeys.documents.detail(documentId),
      });
    },
  });
}

/**
 * Hook to retrieve exact source evidence chunk by ID for citation inspection.
 * Lazy loaded when citation drawer is active.
 */
export function useCitationChunk(
  chunkId: string | null,
  options?: Partial<UseQueryOptions<DocumentChunkResponse, Error>>
) {
  return useQuery({
    queryKey: queryKeys.documents.chunk(chunkId || ""),
    queryFn: ({ signal }) => {
      if (!chunkId) throw new Error("Chunk ID is required for citation inspection");
      return documentsApi.getChunk(chunkId, signal);
    },
    enabled: Boolean(chunkId),
    staleTime: 5 * 60 * 1000, // 5 minutes cache
    ...options,
  });
}
