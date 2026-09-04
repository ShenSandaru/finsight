import { apiClient } from "./client";
import type { HealthResponse } from "@/types/api";

/**
 * Health & Diagnostics API Service
 * 
 * Maps directly to backend/app/main.py GET /health
 */
export const healthApi = {
  /**
   * Health check endpoint
   * GET /health
   */
  async check(signal?: AbortSignal): Promise<HealthResponse> {
    return apiClient<HealthResponse>("/health", {
      signal,
    });
  },
};
