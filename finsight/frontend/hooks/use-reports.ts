import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { reportsApi } from "@/lib/api/reports";
import { queryKeys } from "@/lib/api/query-keys";
import type {
  ReportResponse,
  ReportListResponse,
  CreateReportRequest,
  ListReportsParams,
} from "@/types/api";

/**
 * Hook to list reports with optional status filtering and pagination
 */
export function useReports(
  params: ListReportsParams = {},
  options?: Partial<UseQueryOptions<ReportListResponse, Error>>
) {
  return useQuery({
    queryKey: queryKeys.reports.list(params),
    queryFn: ({ signal }) => reportsApi.list(params, signal),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      // Auto-poll every 3s if any report is pending or processing
      const hasActive = data.reports.some(
        (r) => r.status === "pending" || r.status === "processing"
      );
      return hasActive ? 3000 : false;
    },
    ...options,
  });
}

/**
 * Hook to fetch a single report with smart polling until completion or failure
 */
export function useReport(
  reportId: string,
  options?: Partial<UseQueryOptions<ReportResponse, Error>>
) {
  return useQuery({
    queryKey: queryKeys.reports.detail(reportId),
    queryFn: ({ signal }) => reportsApi.get(reportId, signal),
    enabled: Boolean(reportId),
    refetchInterval: (query) => {
      const report = query.state.data;
      if (!report) return false;
      // Poll every 2s while report is pending or processing
      if (report.status === "pending" || report.status === "processing") {
        return 2000;
      }
      // Stop polling once completed or failed
      return false;
    },
    ...options,
  });
}

/**
 * Mutation hook to create and enqueue an asynchronous report
 */
export function useCreateReport() {
  const queryClient = useQueryClient();

  return useMutation<ReportResponse, Error, CreateReportRequest>({
    mutationFn: (request) => reportsApi.create(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.reports.all() });
    },
  });
}

/**
 * Mutation hook to delete a report
 */
export function useDeleteReport() {
  const queryClient = useQueryClient();

  return useMutation<null, Error, string>({
    mutationFn: (reportId) => reportsApi.delete(reportId),
    onSuccess: (_, reportId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.reports.all() });
      queryClient.removeQueries({
        queryKey: queryKeys.reports.detail(reportId),
      });
    },
  });
}
