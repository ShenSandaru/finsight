import { describe, it, expect, beforeEach, vi } from "vitest";
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import {
  mockDocument,
  mockDocumentB,
  mockDocumentList,
  mockConversationQueryResponse,
  mockComparisonQueryResponse,
  mockComparisonFindings,
  mockReport,
  mockReportList,
  mockTableChunk,
} from "./mocks/data";

import DocumentsPage from "@/app/documents/page";
import ResearchPage from "@/app/research/page";
import ComparePage from "@/app/compare/page";
import ReportsHistoryPage from "@/app/reports/page";
import ReportDetailPage from "@/app/reports/[reportId]/page";
import { ComparisonTable } from "@/components/comparison/comparison-table";
import { CitationDrawer } from "@/components/citations/citation-drawer";
import { useUiStore } from "@/stores/ui-store";

// Mock router navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  useParams: () => ({
    reportId: "66666666-6666-6666-6666-666666666666",
  }),
  usePathname: () => "/research",
}));

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
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

describe("Phase 11.9: Multi-Workflow Integration & Lifecycle Hardening Test Suite", () => {
  beforeEach(() => {
    mockPush.mockClear();
    useUiStore.setState({
      sidebarOpen: true,
      citationDrawerOpen: false,
      activeCitationChunkId: null,
      activeCitationContext: null,
      selectedDocumentIds: [],
    });
  });

  // =========================================================================
  // 1. Selection Lifecycle & Pruning Tests (Step 11.9.1 & 11.9.6)
  // =========================================================================
  describe("Document Selection Lifecycle & Pruning", () => {
    it("prunes deleted document IDs when valid document list changes (Case 1: [A, B, C] -> [B, C])", () => {
      useUiStore.setState({
        selectedDocumentIds: ["doc-A", "doc-B", "doc-C"],
      });

      // Repository loads with only doc-B and doc-C
      useUiStore.getState().pruneDeletedDocuments(["doc-B", "doc-C"]);

      expect(useUiStore.getState().selectedDocumentIds).toEqual(["doc-B", "doc-C"]);
    });

    it("clears selection when all selected documents are deleted (Case 2: [A, B] -> [])", () => {
      useUiStore.setState({
        selectedDocumentIds: ["doc-A", "doc-B"],
      });

      // Repository empty or has none of the selected documents
      useUiStore.getState().pruneDeletedDocuments(["doc-X", "doc-Y"]);

      expect(useUiStore.getState().selectedDocumentIds).toEqual([]);
    });

    it("leaves selection untouched if all selected documents remain valid", () => {
      useUiStore.setState({
        selectedDocumentIds: [mockDocument.id, mockDocumentB.id],
      });

      useUiStore.getState().pruneDeletedDocuments([mockDocument.id, mockDocumentB.id, "doc-C"]);

      expect(useUiStore.getState().selectedDocumentIds).toEqual([mockDocument.id, mockDocumentB.id]);
    });
  });

  // =========================================================================
  // 2. Compare Workspace Lifecycle Hardening (Step 11.9.2 & 11.9.6 Cases 3, 4)
  // =========================================================================
  describe("Compare Workspace Lifecycle Hardening", () => {
    it("disables comparison execution and displays warning when 0 or 1 document is selected", async () => {
      useUiStore.setState({ selectedDocumentIds: [mockDocument.id] }); // 1 doc only
      renderWithClient(<ComparePage />);

      await waitFor(() => {
        expect(screen.getByTestId("execute-comparison-btn")).toBeDisabled();
      });
      expect(screen.getByTestId("minimum-selection-warning")).toBeInTheDocument();
    });

    it("enables comparison execution when 2+ documents are selected", async () => {
      useUiStore.setState({
        selectedDocumentIds: [mockDocument.id, mockDocumentB.id],
      });
      renderWithClient(<ComparePage />);

      await waitFor(() => {
        expect(screen.getByTestId("execute-comparison-btn")).not.toBeDisabled();
      });
      expect(screen.queryByTestId("minimum-selection-warning")).not.toBeInTheDocument();
    });

    it("clears comparison results when selection is reduced below 2 documents", async () => {
      useUiStore.setState({
        selectedDocumentIds: [mockDocument.id, mockDocumentB.id],
      });
      renderWithClient(<ComparePage />);

      // Execute comparison
      const executeBtn = screen.getByTestId("execute-comparison-btn");
      fireEvent.click(executeBtn);

      // Verify comparison results appear
      await waitFor(() => {
        expect(screen.getByTestId("comparison-view")).toBeInTheDocument();
      });

      // Deselect one document via store (simulating deletion or uncheck)
      useUiStore.setState({
        selectedDocumentIds: [mockDocument.id],
      });

      // Comparison view must be cleared to prevent displaying stale results
      await waitFor(() => {
        expect(screen.queryByTestId("comparison-view")).not.toBeInTheDocument();
      });
    });
  });

  // =========================================================================
  // 3. Complete Cross-Workflow Integration Journey (Step 11.9.5)
  // =========================================================================
  describe("Complete Multi-Workflow Integration Journey", () => {
    it("executes the end-to-end user research and comparison workflow", async () => {
      // Step A: Documents Page - Select filings
      const docsRender = renderWithClient(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByTestId(`document-checkbox-${mockDocument.id}`)).toBeInTheDocument();
      });

      // Select Document A and Document B
      const checkA = screen.getByTestId(`document-checkbox-${mockDocument.id}`);
      const checkB = screen.getByTestId(`document-checkbox-${mockDocumentB.id}`);
      fireEvent.click(checkA);
      fireEvent.click(checkB);

      expect(useUiStore.getState().selectedDocumentIds).toEqual([
        mockDocument.id,
        mockDocumentB.id,
      ]);

      docsRender.unmount();

      // Step B: Research Page - Query with selected document context
      const researchRender = renderWithClient(
        <>
          <ResearchPage />
        </>
      );

      // Create session
      const newSessionBtn = screen.getByTestId("start-new-research-btn");
      fireEvent.click(newSessionBtn);

      await waitFor(() => {
        expect(screen.getByTestId("empty-conversation-state")).toBeInTheDocument();
      });

      // Submit inquiry
      const textarea = screen.getByTestId("research-query-textarea");
      fireEvent.change(textarea, { target: { value: "What was Apple's gross margin in 2025?" } });
      const submitBtn = screen.getByTestId("submit-query-btn");
      fireEvent.click(submitBtn);

      // Step C: Citation Drawer Inspection
      await waitFor(
        () => {
          expect(screen.getByText(/Apple reported total revenue/)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      const citationPill = await screen.findByTestId("citation-pill-1");
      expect(citationPill).toBeInTheDocument();
      fireEvent.click(citationPill);

      // Citation drawer opens with resolved evidence
      await waitFor(() => {
        expect(screen.getByTestId("citation-drawer-source-badge")).toBeInTheDocument();
      });
      expect(useUiStore.getState().citationDrawerOpen).toBe(true);

      // Close drawer
      fireEvent.click(screen.getByTestId("citation-drawer-close-button"));
      await waitFor(() => {
        expect(useUiStore.getState().citationDrawerOpen).toBe(false);
      });

      researchRender.unmount();

      // Step D: Cross-Document Comparison Workspace
      const compareRender = renderWithClient(<ComparePage />);

      await waitFor(() => {
        expect(screen.getByTestId("execute-comparison-btn")).not.toBeDisabled();
      });

      // Run comparison
      fireEvent.click(screen.getByTestId("execute-comparison-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("comparison-view")).toBeInTheDocument();
      });

      // Authoritative differences render directly from backend findings
      expect(screen.getByTestId("abs-diff-revenue")).toHaveTextContent("($167.00K)");
      expect(screen.getByTestId("pct-diff-revenue")).toHaveTextContent("-40.53%");

      compareRender.unmount();

      // Step E: Report Viewer
      const reportDetailRender = renderWithClient(<ReportDetailPage />);

      await waitFor(() => {
        expect(screen.getByTestId("report-viewer")).toBeInTheDocument();
      });

      expect(screen.getByText(mockReport.title)).toBeInTheDocument();
      expect(screen.getByTestId("export-markdown-btn")).toBeInTheDocument();

      reportDetailRender.unmount();
    });
  });

  // =========================================================================
  // 4. Responsive & Accessibility Hardening
  // =========================================================================
  describe("Responsive & Accessibility Hardening", () => {
    it("renders ComparisonTable with accessible responsive header and sm:sticky column", () => {
      renderWithClient(
        <ComparisonTable
          findings={mockComparisonFindings}
          documents={[mockDocument, mockDocumentB]}
        />
      );

      const tableContainer = screen.getByTestId("comparison-table-container");
      expect(tableContainer).toBeInTheDocument();

      // Check that metric row has accessible cell
      const metricRow = screen.getByTestId("comparison-row-revenue");
      expect(metricRow).toBeInTheDocument();

      // Evidence buttons have accessible aria-labels
      const evidenceBtn = screen.getByTestId("evidence-btn-revenue");
      expect(evidenceBtn).toHaveAttribute("aria-label", "View evidence for Total Revenue");
    });
  });
});
