import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { conversationsApi } from "@/lib/api/conversations";
import { queryKeys } from "@/lib/api/query-keys";
import type {
  ConversationSessionResponse,
  ConversationMessageResponse,
  CreateSessionRequest,
  ConversationQueryRequest,
  ConversationQueryResponse,
  DeleteSessionResponse,
} from "@/types/api";

/**
 * Hook to get conversation session metadata
 */
export function useConversationSession(
  sessionId: string,
  options?: Partial<UseQueryOptions<ConversationSessionResponse, Error>>
) {
  return useQuery({
    queryKey: queryKeys.conversations.detail(sessionId),
    queryFn: ({ signal }) => conversationsApi.getSession(sessionId, signal),
    enabled: Boolean(sessionId),
    ...options,
  });
}

/**
 * Hook to get chronological message history for a session
 */
export function useConversationMessages(
  sessionId: string,
  limit = 50,
  options?: Partial<UseQueryOptions<ConversationMessageResponse[], Error>>
) {
  return useQuery({
    queryKey: queryKeys.conversations.messages(sessionId, limit),
    queryFn: ({ signal }) =>
      conversationsApi.getMessages(sessionId, limit, signal),
    enabled: Boolean(sessionId),
    ...options,
  });
}

/**
 * Mutation hook to create a new session
 */
export function useCreateSession() {
  const queryClient = useQueryClient();

  return useMutation<ConversationSessionResponse, Error, CreateSessionRequest | undefined>({
    mutationFn: (request) => conversationsApi.createSession(request),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversations.all(),
      });
    },
  });
}

/**
 * Mutation hook to delete a session
 */
export function useDeleteSession() {
  const queryClient = useQueryClient();

  return useMutation<DeleteSessionResponse, Error, string>({
    mutationFn: (sessionId) => conversationsApi.deleteSession(sessionId),
    onSuccess: (_, sessionId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversations.all(),
      });
      queryClient.removeQueries({
        queryKey: queryKeys.conversations.detail(sessionId),
      });
    },
  });
}

/**
 * Mutation hook to submit a multi-turn query in a session
 */
export function useConversationQuery(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation<
    ConversationQueryResponse,
    Error,
    ConversationQueryRequest
  >({
    mutationFn: (request) =>
      conversationsApi.querySession(sessionId, request),
    onSuccess: () => {
      // Invalidate message history and session metadata for the active session
      queryClient.invalidateQueries({
        queryKey: ["conversations", "messages", sessionId],
        exact: false,
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversations.detail(sessionId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversations.all(),
      });
    },
  });
}
