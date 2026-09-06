import type {
  DocumentResponse,
  DocumentListResponse,
  DocumentUploadResponse,
  SearchResponse,
  RAGResponseSchema,
  ConversationSessionResponse,
  ConversationMessageResponse,
  ConversationQueryResponse,
  ReportResponse,
  ReportListResponse,
  HealthResponse,
  DocumentChunkResponse,
  FinancialFinding,
} from "@/types/api";

export const mockHealthResponse: HealthResponse = {
  status: "healthy",
  app: "FinSight",
  version: "0.1.0",
};

export const mockDocument: DocumentResponse = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "apple_10k_2025.pdf",
  file_type: "pdf",
  file_size: 1048576,
  title: "Apple Inc. FY2025 Form 10-K",
  description: "Annual Report for fiscal year ended September 27, 2025",
  source: "SEC EDGAR",
  status: "indexed",
  processing_error: null,
  total_pages: 74,
  total_chunks: 142,
  created_at: "2026-08-24T10:00:00Z",
  updated_at: "2026-08-24T10:02:00Z",
};

export const mockDocumentB: DocumentResponse = {
  id: "22222222-2222-2222-2222-222222222222",
  filename: "microsoft_10k_2025.pdf",
  file_type: "pdf",
  file_size: 2097152,
  title: "Microsoft Corp FY2025 10-K",
  description: "Annual report",
  source: "SEC EDGAR",
  status: "indexed",
  processing_error: null,
  total_pages: 68,
  total_chunks: 120,
  created_at: "2026-08-24T10:05:00Z",
  updated_at: "2026-08-24T10:05:30Z",
};

export const mockDocumentList: DocumentListResponse = {
  total: 2,
  documents: [mockDocument, mockDocumentB],
};

export const mockProcessingDocument: DocumentResponse = {
  id: "88888888-8888-8888-8888-888888888888",
  filename: "nvidia_10k_2025.pdf",
  file_type: "pdf",
  file_size: 1572864,
  title: "NVIDIA Corp FY2025 10-K",
  description: "Annual report",
  source: "SEC EDGAR",
  status: "processing",
  processing_error: null,
  total_pages: null,
  total_chunks: null,
  created_at: "2026-08-24T10:06:00Z",
  updated_at: "2026-08-24T10:06:30Z",
};

export const mockDocumentUploadResponse: DocumentUploadResponse = {
  message: "Document uploaded successfully",
  document: mockProcessingDocument,
};

export const mockSearchResponse: SearchResponse = {
  query: "What was the total revenue in 2025?",
  total_results: 1,
  results: [
    {
      chunk_id: "33333333-3333-3333-3333-333333333333",
      document_id: "11111111-1111-1111-1111-111111111111",
      content: "Total net sales were $412,000 million in fiscal year 2025.",
      chunk_type: "text",
      chunk_index: 12,
      page_number: 28,
      similarity: 0.892,
      metadata: { section: "Item 7: MD&A" },
    },
  ],
};

export const mockRagResponse: RAGResponseSchema = {
  query: "What was Apple's revenue in 2025?",
  answer: "In fiscal year 2025, Apple reported total net sales of $412.0 billion [SOURCE 1].",
  citations: [
    {
      chunk_id: "33333333-3333-3333-3333-333333333333",
      document_id: "11111111-1111-1111-1111-111111111111",
      page_number: 28,
      chunk_type: "text",
      similarity: 0.892,
      statement_type: "income_statement",
      fiscal_periods: ["2025"],
    },
  ],
  retrieved_chunks: 1,
  grounded: true,
};

export const mockSession: ConversationSessionResponse = {
  id: "44444444-4444-4444-4444-444444444444",
  title: "Apple FY2025 Margin Analysis",
  created_at: "2026-08-24T10:10:00Z",
  updated_at: "2026-08-24T10:15:00Z",
  message_count: 2,
};

export const mockMessages: ConversationMessageResponse[] = [
  {
    id: "55555555-5555-5555-5555-555555555551",
    session_id: "44444444-4444-4444-4444-444444444444",
    role: "user",
    content: "What was Apple's gross margin in 2025?",
    created_at: "2026-08-24T10:10:05Z",
  },
  {
    id: "55555555-5555-5555-5555-555555555552",
    session_id: "44444444-4444-4444-4444-444444444444",
    role: "assistant",
    content: "Apple's gross margin for FY2025 was 46.23% [SOURCE 1].",
    created_at: "2026-08-24T10:10:10Z",
  },
];

export const mockFinancialFindings: FinancialFinding[] = [
  {
    metric: "revenue",
    period: "2025",
    value: 412000,
    unit: "$",
    document_id: "11111111-1111-1111-1111-111111111111",
    source_chunk_ids: ["33333333-3333-3333-3333-333333333333"],
  },
  {
    metric: "revenue_growth",
    period: "2025_vs_2024",
    value: 7.49,
    unit: "%",
    document_id: "11111111-1111-1111-1111-111111111111",
    source_chunk_ids: ["33333333-3333-3333-3333-333333333333"],
    calculation: "((412000 - 383285) / 383285) * 100",
  },
  {
    metric: "gross_margin",
    period: "2025",
    value: 46.23,
    unit: "%",
    document_id: "11111111-1111-1111-1111-111111111111",
    source_chunk_ids: ["77777777-7777-7777-7777-777777777777"],
    calculation: "(190500 / 412000) * 100",
  },
  {
    metric: "operating_margin",
    period: "2025",
    value: 30.74,
    unit: "%",
    document_id: "11111111-1111-1111-1111-111111111111",
    source_chunk_ids: ["77777777-7777-7777-7777-777777777777"],
    calculation: "(126600 / 412000) * 100",
  },
  {
    metric: "revenue_cagr",
    period: "2023_to_2025",
    value: 3.75,
    unit: "%",
    document_id: "11111111-1111-1111-1111-111111111111",
    source_chunk_ids: ["33333333-3333-3333-3333-333333333333"],
    calculation: "((412000 / 383285) ^ (1 / 2) - 1) * 100",
  },
  {
    metric: "revenue_trend",
    period: "2023_to_2025",
    value: 1.0,
    unit: "trend",
    document_id: "11111111-1111-1111-1111-111111111111",
    source_chunk_ids: ["33333333-3333-3333-3333-333333333333"],
    calculation: "Consistent Increase: [383285 -> 394328 -> 412000]",
  },
];

export const mockComparisonFindings: FinancialFinding[] = [
  // Document A (Apple) Base Findings
  {
    metric: "revenue",
    period: "2025",
    value: 412000,
    unit: "$",
    document_id: "11111111-1111-1111-1111-111111111111",
    source_chunk_ids: ["33333333-3333-3333-3333-333333333333"],
  },
  {
    metric: "gross_margin",
    period: "2025",
    value: 46.23,
    unit: "%",
    document_id: "11111111-1111-1111-1111-111111111111",
    source_chunk_ids: ["77777777-7777-7777-7777-777777777777"],
  },
  // Document B (Microsoft) Base Findings
  {
    metric: "revenue",
    period: "2025",
    value: 245000,
    unit: "$",
    document_id: "22222222-2222-2222-2222-222222222222",
    source_chunk_ids: ["44444444-4444-4444-4444-444444444444"],
  },
  {
    metric: "gross_margin",
    period: "2025",
    value: 69.45,
    unit: "%",
    document_id: "22222222-2222-2222-2222-222222222222",
    source_chunk_ids: ["44444444-4444-4444-4444-444444444444"],
  },
  // Backend Deterministic Cross-Document Absolute Differences
  {
    metric: "revenue_absolute_difference",
    period: "2025_docB_vs_docA",
    value: -167000,
    unit: "$",
    document_id: null,
    source_chunk_ids: [
      "33333333-3333-3333-3333-333333333333",
      "44444444-4444-4444-4444-444444444444",
    ],
    calculation: "245000 - 412000 [DocB (22222222) vs DocA (11111111)]",
  },
  {
    metric: "gross_margin_absolute_difference",
    period: "2025_docB_vs_docA",
    value: 23.22,
    unit: "%",
    document_id: null,
    source_chunk_ids: [
      "77777777-7777-7777-7777-777777777777",
      "44444444-4444-4444-4444-444444444444",
    ],
    calculation: "69.45 - 46.23 [DocB (22222222) vs DocA (11111111)]",
  },
  // Backend Deterministic Cross-Document Percentage Comparisons
  {
    metric: "revenue_comparison",
    period: "2025_docB_vs_docA",
    value: -40.53,
    unit: "%",
    document_id: null,
    source_chunk_ids: [
      "33333333-3333-3333-3333-333333333333",
      "44444444-4444-4444-4444-444444444444",
    ],
    calculation: "((245000 - 412000) / 412000) * 100 [DocB vs DocA]",
  },
  {
    metric: "gross_margin_comparison",
    period: "2025_docB_vs_docA",
    value: 50.23,
    unit: "%",
    document_id: null,
    source_chunk_ids: [
      "77777777-7777-7777-7777-777777777777",
      "44444444-4444-4444-4444-444444444444",
    ],
    calculation: "((69.45 - 46.23) / 46.23) * 100 [DocB vs DocA]",
  },
];

export const mockConversationQueryResponse: ConversationQueryResponse = {
  session_id: "44444444-4444-4444-4444-444444444444",
  query: "What was Apple's gross margin in 2025?",
  resolved_query: "Apple gross margin FY2025",
  answer: "Apple's gross margin for FY2025 was 46.23% [SOURCE 1].",
  citations: [
    {
      chunk_id: "33333333-3333-3333-3333-333333333333",
      document_id: "11111111-1111-1111-1111-111111111111",
      page_number: 28,
      chunk_type: "table",
      similarity: 0.915,
      statement_type: "income_statement",
      fiscal_periods: ["2025"],
    },
  ],
  findings: mockFinancialFindings,
  retrieved_chunks: 1,
  grounded: true,
};

export const mockComparisonQueryResponse: ConversationQueryResponse = {
  session_id: "44444444-4444-4444-4444-444444444444",
  query: "Compare Apple and Microsoft total revenue and gross margin in 2025.",
  resolved_query: "Compare Apple and Microsoft total revenue and gross margin in 2025",
  answer:
    "In fiscal year 2025, Apple reported total revenue of $412.00B [SOURCE 1] compared to Microsoft's $245.00B [SOURCE 2]. Microsoft demonstrated higher gross margins at 69.45% vs Apple's 46.23%.",
  citations: [
    {
      chunk_id: "33333333-3333-3333-3333-333333333333",
      document_id: "11111111-1111-1111-1111-111111111111",
      page_number: 28,
      chunk_type: "text",
      similarity: 0.94,
      statement_type: "income_statement",
      fiscal_periods: ["2025"],
    },
    {
      chunk_id: "44444444-4444-4444-4444-444444444444",
      document_id: "22222222-2222-2222-2222-222222222222",
      page_number: 35,
      chunk_type: "text",
      similarity: 0.91,
      statement_type: "income_statement",
      fiscal_periods: ["2025"],
    },
  ],
  findings: mockComparisonFindings,
  retrieved_chunks: 2,
  grounded: true,
};

export const mockReport: ReportResponse = {
  id: "66666666-6666-6666-6666-666666666666",
  title: "Apple FY2025 Comprehensive Financial Research Report",
  query: "Comprehensive financial performance and ratio analysis of Apple Inc for FY2025",
  report_type: "financial_research",
  status: "completed",
  document_ids: ["11111111-1111-1111-1111-111111111111"],
  executive_summary: "Apple achieved record revenue and expanded gross margins.",
  findings: [
    {
      metric: "gross_margin",
      period: "2025",
      value: 46.23,
      unit: "%",
      document_id: "11111111-1111-1111-1111-111111111111",
      source_chunk_ids: ["33333333-3333-3333-3333-333333333333"],
      calculation: "gross_profit / revenue * 100",
    },
  ],
  content: "# Financial Research Report\n\n## Executive Summary\n...",
  citations: [
    {
      chunk_id: "33333333-3333-3333-3333-333333333333",
      document_id: "11111111-1111-1111-1111-111111111111",
      page_number: 28,
      chunk_type: "text",
      similarity: 0.92,
      statement_type: "income_statement",
      fiscal_periods: ["2025"],
    },
  ],
  error_message: null,
  created_at: "2026-08-24T10:20:00Z",
  updated_at: "2026-08-24T10:21:00Z",
};

export const mockReportList: ReportListResponse = {
  total: 1,
  reports: [mockReport],
};

export const mockTextChunk: DocumentChunkResponse = {
  id: "33333333-3333-3333-3333-333333333333",
  document_id: "11111111-1111-1111-1111-111111111111",
  document_title: "Apple Inc. FY2025 Form 10-K",
  document_filename: "apple_10k_2025.pdf",
  content: "Total net sales were $412,000 million in fiscal year 2025, compared to $383,285 million in 2024.",
  chunk_type: "text",
  chunk_index: 12,
  page_number: 28,
  metadata: {
    section: "Item 7. Management's Discussion and Analysis",
    period: "FY2025",
  },
  created_at: "2026-08-24T10:02:00Z",
};

export const mockTableChunk: DocumentChunkResponse = {
  id: "77777777-7777-7777-7777-777777777777",
  document_id: "11111111-1111-1111-1111-111111111111",
  document_title: "Apple Inc. FY2025 Form 10-K",
  document_filename: "apple_10k_2025.pdf",
  content: "| Line Item | FY2025 ($M) | FY2024 ($M) |\n| :--- | :--- | :--- |\n| Total Net Sales | $412,000 | $383,285 |\n| Cost of Sales | $221,500 | $210,350 |\n| Gross Margin | $190,500 | $172,935 |\n| Gross Margin % | 46.23% | 45.12% |",
  chunk_type: "table",
  chunk_index: 15,
  page_number: 29,
  metadata: {
    table_title: "Consolidated Statements of Operations",
    statement_type: "income_statement",
    fiscal_periods: ["2025", "2024"],
  },
  created_at: "2026-08-24T10:02:05Z",
};

export const mockUser = {
  id: "user-1111-1111-1111-111111111111",
  email: "analyst@finsight.com",
  name: "FinSight Analyst",
  image_url: null,
  provider: "google",
  provider_sub: "google-analyst-12345",
  is_active: true,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};
