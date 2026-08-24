/**
 * FinSight API Client Foundation
 * 
 * Centralized, type-safe API communication layer with normalized error handling.
 * Browser-safe: Reads ONLY NEXT_PUBLIC_API_URL and never touches secret keys.
 */

export class ApiError extends Error {
  public code: string;
  public status: number;
  public details?: unknown;

  constructor(message: string, status: number, code = "API_ERROR", details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, headers, ...customConfig } = options;

  let url = `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const defaultHeaders: HeadersInit = {
    Accept: "application/json",
  };

  // Only set Content-Type if body is not FormData
  if (!(customConfig.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const config: RequestInit = {
    method: "GET",
    headers: {
      ...defaultHeaders,
      ...headers,
    },
    ...customConfig,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorData: { error?: { code?: string; message?: string; details?: unknown } } | null = null;
      try {
        errorData = await response.json();
      } catch {
        // Response was not JSON
      }

      const errorMessage =
        errorData?.error?.message ||
        `Request failed with status ${response.status} (${response.statusText})`;
      const errorCode = errorData?.error?.code || `HTTP_${response.status}`;
      const errorDetails = errorData?.error?.details;

      throw new ApiError(errorMessage, response.status, errorCode, errorDetails);
    }

    if (response.status === 204) {
      return null as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      error instanceof Error ? error.message : "Network error or unexpected failure",
      0,
      "NETWORK_ERROR"
    );
  }
}
