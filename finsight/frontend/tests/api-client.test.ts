import { describe, it, expect } from "vitest";
import { apiClient, ApiError } from "@/lib/api/client";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";

describe("API Client Foundation Tests", () => {
  it("executes GET requests and parses JSON responses", async () => {
    const res = await apiClient<{ status: string }>("/health");
    expect(res).toBeDefined();
    expect(res.status).toBe("healthy");
  });

  it("serializes query parameters correctly in URLs", async () => {
    server.use(
      http.get("*/api/test-params", ({ request }) => {
        const url = new URL(request.url);
        return HttpResponse.json({
          status: url.searchParams.get("status"),
          limit: url.searchParams.get("limit"),
        });
      })
    );

    const res = await apiClient<{ status: string; limit: string }>(
      "/api/test-params",
      {
        params: { status: "completed", limit: 20, ignored: null },
      }
    );

    expect(res.status).toBe("completed");
    expect(res.limit).toBe("20");
  });

  it("handles HTTP 204 No Content responses cleanly as null", async () => {
    const res = await apiClient<null>(
      "/api/v1/documents/11111111-1111-1111-1111-111111111111",
      {
        method: "DELETE",
      }
    );
    expect(res).toBeNull();
  });

  it("normalizes backend 404 structured errors into typed ApiError", async () => {
    try {
      await apiClient("/api/v1/documents/not-found");
      expect.fail("Should have thrown ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(404);
      expect(apiErr.code).toBe("NOT_FOUND");
      expect(apiErr.message).toBe("Document not found");
      expect(apiErr.details).toEqual({ document_id: "not-found" });
    }
  });

  it("normalizes backend 422 validation errors into ApiError", async () => {
    server.use(
      http.post("*/api/test-validation", () => {
        return HttpResponse.json(
          {
            error: {
              code: "UNPROCESSABLE_ENTITY",
              message: "Request validation failed",
              details: [{ loc: ["body", "query"], msg: "Field required" }],
            },
          },
          { status: 422 }
        );
      })
    );

    try {
      await apiClient("/api/test-validation", { method: "POST" });
      expect.fail("Should have thrown ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(422);
      expect(apiErr.code).toBe("UNPROCESSABLE_ENTITY");
      expect(Array.isArray(apiErr.details)).toBe(true);
    }
  });

  it("handles network failures safely without throwing raw exceptions", async () => {
    server.use(
      http.get("*/api/test-network-error", () => {
        return HttpResponse.error();
      })
    );

    try {
      await apiClient("/api/test-network-error");
      expect.fail("Should have thrown ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.code).toBe("NETWORK_ERROR");
      expect(apiErr.status).toBe(0);
    }
  });

  it("does not set Content-Type to application/json when body is FormData", async () => {
    server.use(
      http.post("*/api/test-form", ({ request }) => {
        const contentType = request.headers.get("content-type");
        const accept = request.headers.get("accept");
        return HttpResponse.json({
          contentType,
          accept,
        });
      })
    );

    const form = new FormData();
    form.append("testKey", "testValue");

    const res = await apiClient<{ contentType: string | null; accept: string | null }>(
      "/api/test-form",
      {
        method: "POST",
        body: form,
      }
    );

    expect(res.accept).toBe("application/json");
    // Ensure application/json was NOT set as Content-Type for FormData
    expect(res.contentType).not.toBe("application/json");
  });

  it("supports request cancellation using AbortController", async () => {
    const controller = new AbortController();
    controller.abort();

    try {
      await apiClient("/health", { signal: controller.signal });
      expect.fail("Should have aborted");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.code).toBe("NETWORK_ERROR");
    }
  });
});
