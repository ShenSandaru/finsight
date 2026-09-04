import { apiClient } from "./client";
import type {
  DocumentResponse,
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentUploadParams,
} from "@/types/api";

/**
 * Documents Domain API Service
 * 
 * Maps directly to backend/app/api/routes/documents.py
 */
export const documentsApi = {
  /**
   * Fetch list of all uploaded documents
   * GET /api/v1/documents/
   */
  async list(signal?: AbortSignal): Promise<DocumentListResponse> {
    return apiClient<DocumentListResponse>("/api/v1/documents/", {
      signal,
    });
  },

  /**
   * Get metadata and indexing status for a single document
   * GET /api/v1/documents/{id}
   */
  async get(documentId: string, signal?: AbortSignal): Promise<DocumentResponse> {
    return apiClient<DocumentResponse>(`/api/v1/documents/${documentId}`, {
      signal,
    });
  },

  /**
   * Upload a new financial document (PDF, TXT, CSV)
   * POST /api/v1/documents/upload
   */
  async upload(
    params: DocumentUploadParams,
    signal?: AbortSignal
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", params.file);
    if (params.title) formData.append("title", params.title);
    if (params.description) formData.append("description", params.description);
    if (params.source) formData.append("source", params.source);

    return apiClient<DocumentUploadResponse>("/api/v1/documents/upload", {
      method: "POST",
      body: formData,
      signal,
    });
  },

  /**
   * Delete a document and cascade delete its chunks
   * DELETE /api/v1/documents/{id}
   */
  async delete(documentId: string, signal?: AbortSignal): Promise<null> {
    return apiClient<null>(`/api/v1/documents/${documentId}`, {
      method: "DELETE",
      signal,
    });
  },
};
