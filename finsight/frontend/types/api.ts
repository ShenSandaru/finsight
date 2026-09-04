/**
 * FinSight Backend API TypeScript Contracts
 * 
 * Sourced directly from FastAPI Pydantic schemas (Sprint 6 through Sprint 10.5).
 * Acts as the strict frontend type foundation for all API requests and responses.
 */

// ==========================================
// 1. Common / Error Types
// ==========================================

export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown> | Array<unknown> | null;
}

export interface ErrorResponse {
  error: ErrorDetail;
}

// ==========================================
// 2. Health Types
// ==========================================

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
}

// ==========================================
// 3. Document Types
// ==========================================

export type DocumentStatus = "pending" | "processing" | "parsed" | "indexed" | "failed";

export interface DocumentResponse {
  id: string; // UUID
  filename: string;
  file_type: string;
  file_size: number;
  title: string | null;
  description: string | null;
  source: string | null;
  status: DocumentStatus | string;
  processing_error: string | null;
  total_pages: number | null;
  total_chunks: number | null;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}

export interface DocumentUploadResponse {
  message: string;
  document: DocumentResponse;
}

export interface DocumentListResponse {
  total: number;
  documents: DocumentResponse[];
}

export interface DocumentChunkResponse {
  id: string; // UUID
  document_id: string; // UUID
  document_title: string | null;
  document_filename: string | null;
  content: string;
  chunk_type: "text" | "table" | string;
  chunk_index: number;
  page_number: number | null;
  metadata?: Record<string, unknown> | null;
  created_at: string; // ISO 8601
}

export interface DocumentUploadParams {
  file: File;
  title?: string;
  description?: string;
  source?: string;
}

// ==========================================
// 4. Search & Retrieval Types
// ==========================================

export interface SearchRequest {
  query: string;
  top_k?: number; // 1 to 20, default 5
  min_similarity?: number; // 0.0 to 1.0, default 0.0
  document_id?: string | null; // UUID
  document_ids?: string[] | null; // UUID[]
}

export interface SearchResultItem {
  chunk_id: string; // UUID
  document_id: string; // UUID
  content: string;
  chunk_type: "text" | "table" | string;
  chunk_index: number;
  page_number: number | null;
  similarity: number; // 0.0 to 1.0
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  total_results: number;
  results: SearchResultItem[];
}

// ==========================================
// 5. RAG & Citation Types
// ==========================================

export interface CitationResponse {
  chunk_id: string; // UUID
  document_id: string; // UUID
  page_number: number | null;
  chunk_type: "text" | "table" | string;
  similarity: number; // 0.0 to 1.0
  statement_type: string | null;
  fiscal_periods: string[];
}

export interface RAGRequest {
  query: string;
  top_k?: number; // 1 to 20, default 5
  min_similarity?: number; // 0.0 to 1.0, default 0.30
  document_id?: string | null; // UUID
  document_ids?: string[] | null; // UUID[]
}

export interface RAGResponseSchema {
  query: string;
  answer: string;
  citations: CitationResponse[];
  retrieved_chunks: number;
  grounded: boolean;
}

// ==========================================
// 6. Conversation Types (Sprint 8.2)
// ==========================================

export interface CreateSessionRequest {
  title?: string | null;
}

export interface ConversationSessionResponse {
  id: string; // UUID
  title: string | null;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
  message_count: number;
}

export interface ConversationMessageResponse {
  id: string; // UUID
  session_id: string; // UUID
  role: "user" | "assistant" | string;
  content: string;
  findings?: FinancialFinding[];
  created_at: string; // ISO 8601
}

export interface ConversationQueryRequest {
  query: string;
  top_k?: number; // 1 to 20, default 5
  min_similarity?: number; // 0.0 to 1.0, default 0.30
  document_id?: string | null; // UUID
  document_ids?: string[] | null; // UUID[]
}

export interface ConversationQueryResponse {
  session_id: string; // UUID
  query: string;
  resolved_query: string | null;
  answer: string;
  citations: CitationResponse[];
  findings?: FinancialFinding[];
  retrieved_chunks: number;
  grounded: boolean;
}

export interface DeleteSessionResponse {
  message: string;
  session_id: string;
}

// ==========================================
// 7. Financial Findings & Research State Types
// ==========================================

export interface FinancialFinding {
  metric: string;
  period: string;
  value: number;
  unit: string;
  document_id?: string | null;
  source_chunk_ids: string[];
  calculation?: string | null;
}

// ==========================================
// 8. Research Report Types (Sprint 10.4)
// ==========================================

export type ReportStatus = "pending" | "processing" | "completed" | "failed";

export interface CreateReportRequest {
  query: string;
  title?: string | null;
  document_ids?: string[] | null;
  report_type?: string; // default: "financial_research"
}

export interface ReportResponse {
  id: string; // UUID
  title: string;
  query: string;
  report_type: string;
  status: ReportStatus | string;
  document_ids: string[] | null;
  executive_summary: string | null;
  findings: FinancialFinding[] | Record<string, unknown>[] | null;
  content: string | null; // Full GitHub Flavored Markdown
  citations: CitationResponse[] | null;
  error_message: string | null;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}

export interface ReportListResponse {
  total: number;
  reports: ReportResponse[];
}

export interface ListReportsParams {
  status?: ReportStatus | string;
  limit?: number; // default 50
  offset?: number; // default 0
}
