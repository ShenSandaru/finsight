import { describe, it, expect, beforeEach, vi } from "vitest";
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { mockReport, mockReportList } from "./mocks/data";
import { ReportStatusBadge } from "@/components/reports/report-status-badge";
import { ReportViewer } from "@/components/reports/report-viewer";
import { GenerateReportModal } from "@/components/reports/generate-report-modal";
import ReportsHistoryPage from "@/app/reports/page";
import ReportDetailPage from "@/app/reports/[reportId]/page";
import { useUiStore } from "@/stores/ui-store";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  useParams: () => ({
    reportId: "99999999-9999-9999-9999-999999999999",
  }),
  usePathname: () => "/reports",
}));

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function renderWithClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return {
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
    queryClient,
  };
}

describe("Phase 11.7: Structured Research Reports UI", () => {
  beforeEach(() => {
    mockPush.mockClear();
    useUiStore.setState({
      citationDrawerOpen: false,
      activeCitationChunkId: null,
      activeCitationContext: null,
      selectedDocumentIds: [],
    });
  });

  describe("ReportStatusBadge Component", () => {
    it("renders completed status badge correctly", () => {
      render(<ReportStatusBadge status="completed" />);
      const badge = screen.getByTestId("report-status-completed");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent("Completed");
    });

    it("renders processing status badge correctly", () => {
      render(<ReportStatusBadge status="processing" />);
      const badge = screen.getByTestId("report-status-processing");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent("Processing");
    });

    it("renders pending status badge correctly", () => {
      render(<ReportStatusBadge status="pending" />);
      const badge = screen.getByTestId("report-status-pending");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent("Pending");
    });

    it("renders failed status badge correctly", () => {
      render(<ReportStatusBadge status="failed" />);
      const badge = screen.getByTestId("report-status-failed");
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent("Failed");
    });
  });

  describe("ReportViewer Component", () => {
    it("renders headings, paragraphs, lists, and tables properly", () => {
      const markdown = `
# Test Report Title
## 1. Executive Summary
This is a test paragraph describing research findings.
- Key bullet 1
- Key bullet 2

## 2. Key Financial Metrics
| Document | Metric | Period | Value | Unit | Formula |
|---|---|---|---|---|---|
| Primary | gross_margin | 2025 | 46.23 | % | Reported Line Item |
| Primary | net_income | 2025 | 98,500.00 | $M | Net profit |
`;

      render(<ReportViewer content={markdown} citations={mockReport.citations} />);
      expect(screen.getByText("Test Report Title")).toBeInTheDocument();
      expect(screen.getByText("1. Executive Summary")).toBeInTheDocument();
      expect(screen.getByText("This is a test paragraph describing research findings.")).toBeInTheDocument();
      expect(screen.getByText("Key bullet 1")).toBeInTheDocument();
      expect(screen.getByText("Key bullet 2")).toBeInTheDocument();

      // Check table presence
      expect(screen.getByTestId("report-table")).toBeInTheDocument();
      expect(screen.getByText("gross_margin")).toBeInTheDocument();
      expect(screen.getByText("46.23")).toBeInTheDocument();
    });

    it("converts [SOURCE N] citations to CitationPill and opens drawer upon click", async () => {
      const markdown = "Revenue increased as noted in [SOURCE 1].";
      render(<ReportViewer content={markdown} citations={mockReport.citations} />);

      const pill = screen.getByTestId("citation-pill-1");
      expect(pill).toBeInTheDocument();
      expect(screen.getByText("SOURCE 1")).toBeInTheDocument();

      fireEvent.click(pill);

      expect(useUiStore.getState().citationDrawerOpen).toBe(true);
      expect(useUiStore.getState().activeCitationChunkId).toBe("33333333-3333-3333-3333-333333333333");
    });
  });

  describe("GenerateReportModal Component", () => {
    it("submits generation request with document scope and redirects to detail page", async () => {
      useUiStore.setState({ selectedDocumentIds: ["11111111-1111-1111-1111-111111111111"] });
      const onOpenChange = vi.fn();

      renderWithClient(
        <GenerateReportModal
          open={true}
          onOpenChange={onOpenChange}
          defaultQuery="Perform FY2025 Margin Analysis"
          defaultTitle="Apple Margin Analysis"
        />
      );

      expect(screen.getByTestId("generate-report-modal")).toBeInTheDocument();
      expect(screen.getByTestId("generate-report-doc-count")).toHaveTextContent("1 document selected");

      const submitBtn = screen.getByTestId("submit-generate-report-btn");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(onOpenChange).toHaveBeenCalledWith(false);
        expect(mockPush).toHaveBeenCalledWith(`/reports/${mockReport.id}`);
      });
    });

    it("validates minimum query length", async () => {
      const onOpenChange = vi.fn();
      renderWithClient(
        <GenerateReportModal
          open={true}
          onOpenChange={onOpenChange}
          defaultQuery=""
        />
      );

      const submitBtn = screen.getByTestId("submit-generate-report-btn");
      expect(submitBtn).toBeDisabled();
    });
  });

  describe("Reports Listing / History Page", () => {
    it("renders reports list fetched from backend", async () => {
      renderWithClient(<ReportsHistoryPage />);

      await waitFor(() => {
        expect(screen.getByText(mockReport.title)).toBeInTheDocument();
        expect(screen.getByTestId("report-status-completed")).toBeInTheDocument();
      });
    });

    it("filters reports by search query", async () => {
      renderWithClient(<ReportsHistoryPage />);

      await waitFor(() => {
        expect(screen.getByText(mockReport.title)).toBeInTheDocument();
      });

      const searchInput = screen.getByTestId("search-reports-input");
      fireEvent.change(searchInput, { target: { value: "Nonexistent" } });

      await waitFor(() => {
        expect(screen.queryByText(mockReport.title)).not.toBeInTheDocument();
        expect(screen.getByTestId("reports-empty-state")).toBeInTheDocument();
      });
    });
  });

  describe("Report Detail Page", () => {
    it("renders completed report with content, findings, and metadata", async () => {
      renderWithClient(<ReportDetailPage />);

      await waitFor(() => {
        expect(screen.getByTestId("report-detail-title")).toHaveTextContent(mockReport.title);
        expect(screen.getByTestId("export-markdown-btn")).toBeInTheDocument();
        expect(screen.getByTestId("copy-markdown-btn")).toBeInTheDocument();
      });
    });

    it("renders processing state when report status is processing", async () => {
      server.use(
        http.get("*/api/v1/reports/:id", () => {
          return HttpResponse.json({
            ...mockReport,
            status: "processing",
            content: "",
          });
        })
      );

      renderWithClient(<ReportDetailPage />);

      await waitFor(() => {
        expect(screen.getByTestId("report-processing-state")).toBeInTheDocument();
        expect(screen.getByText("Financial Report Generation in Progress")).toBeInTheDocument();
      });
    });

    it("renders failed state when report status is failed", async () => {
      server.use(
        http.get("*/api/v1/reports/:id", () => {
          return HttpResponse.json({
            ...mockReport,
            status: "failed",
            error_message: "Filing parsing timeout exceeded.",
            content: "",
          });
        })
      );

      renderWithClient(<ReportDetailPage />);

      await waitFor(() => {
        expect(screen.getByTestId("report-failed-state")).toBeInTheDocument();
        expect(screen.getByText("Filing parsing timeout exceeded.")).toBeInTheDocument();
      });
    });
  });
});
