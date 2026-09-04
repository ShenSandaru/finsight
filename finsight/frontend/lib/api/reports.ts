import { apiClient } from "./client";
import type {
  ReportResponse,
  ReportListResponse,
  CreateReportRequest,
  ListReportsParams,
} from "@/types/api";

/**
 * Financial Research Reports Domain API Service (Sprint 10.4)
 * 
 * Maps directly to backend/app/api/routes/reports.py
 */
export const reportsApi = {
  /**
   * Create and enqueue an asynchronous financial research report
   * POST /api/v1/reports (Returns HTTP 202 Accepted with status="pending")
   */
  async create(
    request: CreateReportRequest,
    signal?: AbortSignal
  ): Promise<ReportResponse> {
    return apiClient<ReportResponse>("/api/v1/reports", {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    });
  },

  /**
   * Get report status, markdown content, findings, and citations
   * GET /api/v1/reports/{report_id}
   */
  async get(
    reportId: string,
    signal?: AbortSignal
  ): Promise<ReportResponse> {
    return apiClient<ReportResponse>(`/api/v1/reports/${reportId}`, {
      signal,
    });
  },

  /**
   * List reports with optional status filtering and pagination
   * GET /api/v1/reports
   */
  async list(
    params: ListReportsParams = {},
    signal?: AbortSignal
  ): Promise<ReportListResponse> {
    return apiClient<ReportListResponse>("/api/v1/reports", {
      params: {
        status: params.status,
        limit: params.limit,
        offset: params.offset,
      },
      signal,
    });
  },

  /**
   * Delete a report record
   * DELETE /api/v1/reports/{report_id}
   */
  async delete(
    reportId: string,
    signal?: AbortSignal
  ): Promise<null> {
    return apiClient<null>(`/api/v1/reports/${reportId}`, {
      method: "DELETE",
      signal,
    });
  },
};
