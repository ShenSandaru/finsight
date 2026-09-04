import {
  useQuery,
  useMutation,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { searchApi } from "@/lib/api/search";
import { queryKeys } from "@/lib/api/query-keys";
import type { SearchRequest, SearchResponse } from "@/types/api";

/**
 * Hook to execute semantic vector search as a query
 */
export function useSearch(
  params: SearchRequest,
  options?: Partial<UseQueryOptions<SearchResponse, Error>>
) {
  return useQuery({
    queryKey: queryKeys.search(params),
    queryFn: ({ signal }) => searchApi.search(params, signal),
    enabled: Boolean(params.query && params.query.trim().length > 0),
    ...options,
  });
}

/**
 * Mutation hook to trigger on-demand search programmatically
 */
export function useSearchMutation() {
  return useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: (params) => searchApi.search(params),
  });
}
