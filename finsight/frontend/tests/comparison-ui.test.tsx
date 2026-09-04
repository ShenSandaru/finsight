import { describe, it, expect, beforeEach, vi } from "vitest";
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import {
  mockDocument,
  mockDocumentB,
  mockComparisonFindings,
  mockComparisonQueryResponse,
} from "./mocks/data";
import { ComparisonSelector } from "@/components/comparison/comparison-selector";
import { ComparisonTable } from "@/components/comparison/comparison-table";
import { VarianceIndicator } from "@/components/comparison/variance-indicator";
import { ComparisonView } from "@/components/comparison/comparison-view";
import ComparePage from "@/app/compare/page";
import DocumentsPage from "@/app/documents/page";
import { SelectedDocumentContext } from "@/components/research/selected-document-context";
import { useUiStore } from "@/stores/ui-store";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  useParams: () => ({}),
  usePathname: () => "/compare",
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

describe("Phase 11.8: Cross-Document Comparison UX Test Suite", () => {
  beforeEach(() => {
    mockPush.mockClear();
    useUiStore.setState({
      citationDrawerOpen: false,
      activeCitationChunkId: null,
      activeCitationContext: null,
      selectedDocumentIds: [],
    });
  });

  // =========================================================================
  // 1. VarianceIndicator Unit Tests
  // =========================================================================
  describe("VarianceIndicator Presentation Component", () => {
    it("renders positive percentage variance with upward glyph and correct formatting", () => {
      render(<VarianceIndicator value={50.23} unit="%" />);
      const el = screen.getByTestId("variance-indicator");
      expect(el).toHaveTextContent("↑");
      expect(el).toHaveTextContent("+50.23%");
      expect(el.getAttribute("aria-label")).toContain("Positive Variance: +50.23%");
    });

    it("renders negative percentage variance with downward glyph and minus sign", () => {
      render(<VarianceIndicator value={-40.53} unit="%" />);
      const el = screen.getByTestId("variance-indicator");
      expect(el).toHaveTextContent("↓");
      expect(el).toHaveTextContent("-40.53%");
      expect(el.getAttribute("aria-label")).toContain("Negative Variance: -40.53%");
    });

    it("renders flat / zero variance with neutral glyph", () => {
      render(<VarianceIndicator value={0.0} unit="%" />);
      const el = screen.getByTestId("variance-indicator");
      expect(el).toHaveTextContent("→");
      expect(el).toHaveTextContent("0.00%");
      expect(el.getAttribute("aria-label")).toContain("Flat / No Change");
    });

    it("renders currency variances formatted into millions / billions without frontend calculation", () => {
      render(<VarianceIndicator value={-167_000_000} unit="$" />);
      const el = screen.getByTestId("variance-indicator");
      expect(el).toHaveTextContent("↓");
      expect(el).toHaveTextContent("($167.00M)");
    });
  });

  // =========================================================================
  // 2. Document Selection & Constraint Enforcement
  // =========================================================================
  describe("ComparisonSelector & Minimum Constraint", () => {
    it("displays advisory banner when fewer than 2 documents are selected", async () => {
      useUiStore.setState({ selectedDocumentIds: [mockDocument.id] });
      renderWithClient(<ComparisonSelector />);

      await waitFor(() => {
        expect(screen.getByTestId("minimum-selection-warning")).toBeInTheDocument();
      });
      expect(screen.getByTestId("minimum-selection-warning")).toHaveTextContent(
        "Select at least 1 more document to enable cross-document comparison."
      );
    });

    it("enables multi-document selection and displays active document tags", async () => {
      useUiStore.setState({
        selectedDocumentIds: [mockDocument.id, mockDocumentB.id],
      });
      renderWithClient(<ComparisonSelector />);

      await waitFor(() => {
        expect(screen.getByTestId("selected-docs-summary")).toBeInTheDocument();
      });

      expect(screen.queryByTestId("minimum-selection-warning")).not.toBeInTheDocument();
      expect(screen.getByTestId(`selected-tag-${mockDocument.id}`)).toBeInTheDocument();
      expect(screen.getByTestId(`selected-tag-${mockDocumentB.id}`)).toBeInTheDocument();
      expect(screen.getByTestId("selected-count-badge")).toHaveTextContent("2 of 2 selected");
    });

    it("toggles document selection when clicking document cards", async () => {
      renderWithClient(<ComparisonSelector />);

      await waitFor(() => {
        expect(screen.getByTestId(`doc-checkbox-card-${mockDocument.id}`)).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId(`doc-checkbox-card-${mockDocument.id}`));
      expect(useUiStore.getState().selectedDocumentIds).toContain(mockDocument.id);

      fireEvent.click(screen.getByTestId(`doc-checkbox-card-${mockDocument.id}`));
      expect(useUiStore.getState().selectedDocumentIds).not.toContain(mockDocument.id);
    });
  });

  // =========================================================================
  // 3. ComparisonTable & Authoritative Backend Findings
  // =========================================================================
  describe("ComparisonTable Presentation", () => {
    it("renders authoritative backend absolute differences and percentage comparisons", () => {
      renderWithClient(
        <ComparisonTable
          findings={mockComparisonFindings}
          documents={[mockDocument, mockDocumentB]}
        />
      );

      // Revenue Row
      expect(screen.getByTestId("comparison-row-revenue")).toBeInTheDocument();
      // Doc A value ($412,000 -> $412.00K from mock finding value 412000 unit $)
      expect(screen.getByTestId(`cell-revenue-${mockDocument.id}`)).toHaveTextContent("$412.00K");
      // Doc B value ($245,000 -> $245.00K)
      expect(screen.getByTestId(`cell-revenue-${mockDocumentB.id}`)).toHaveTextContent("$245.00K");
      // Backend Authoritative Absolute Difference (-167000 -> ($167.00K))
      expect(screen.getByTestId("abs-diff-revenue")).toHaveTextContent("($167.00K)");
      // Backend Authoritative Percentage Comparison (-40.53%)
      expect(screen.getByTestId("pct-diff-revenue")).toHaveTextContent("-40.53%");

      // Gross Margin Row
      expect(screen.getByTestId("comparison-row-gross_margin")).toBeInTheDocument();
      expect(screen.getByTestId(`cell-gross_margin-${mockDocument.id}`)).toHaveTextContent("+46.23%");
      expect(screen.getByTestId(`cell-gross_margin-${mockDocumentB.id}`)).toHaveTextContent("+69.45%");
      expect(screen.getByTestId("abs-diff-gross_margin")).toHaveTextContent("+23.22%");
      expect(screen.getByTestId("pct-diff-gross_margin")).toHaveTextContent("+50.23%");
    });

    it("triggers existing CitationDrawer when clicking evidence button with source chunk ID", () => {
      renderWithClient(
        <ComparisonTable
          findings={mockComparisonFindings}
          documents={[mockDocument, mockDocumentB]}
        />
      );

      const evidenceBtn = screen.getByTestId("evidence-btn-revenue");
      expect(evidenceBtn).toBeInTheDocument();

      fireEvent.click(evidenceBtn);
      const uiState = useUiStore.getState();
      expect(uiState.citationDrawerOpen).toBe(true);
      expect(uiState.activeCitationChunkId).toBe("33333333-3333-3333-3333-333333333333");
    });

    it("displays informative fallback when no comparable findings exist", () => {
      renderWithClient(<ComparisonTable findings={[]} documents={[mockDocument, mockDocumentB]} />);
      expect(screen.getByTestId("no-comparison-findings")).toBeInTheDocument();
      expect(
        screen.getByText("No comparable financial findings were returned for these filings.")
      ).toBeInTheDocument();
    });
  });

  // =========================================================================
  // 4. Full Compare Workspace Execution Flow
  // =========================================================================
  describe("ComparePage Workspace Integration", () => {
    it("disables comparison button until at least 2 documents are selected", async () => {
      useUiStore.setState({ selectedDocumentIds: [mockDocument.id] });
      renderWithClient(<ComparePage />);

      await waitFor(() => {
        expect(screen.getByTestId("execute-comparison-btn")).toBeDisabled();
      });
    });

    it("executes comparison query when 2+ documents are selected and renders ComparisonView", async () => {
      useUiStore.setState({
        selectedDocumentIds: [],
      });
      renderWithClient(<ComparePage />);

      // Wait for documents to load
      const docCardA = await screen.findByTestId(`doc-checkbox-card-${mockDocument.id}`);
      const docCardB = await screen.findByTestId(`doc-checkbox-card-${mockDocumentB.id}`);

      // Select both documents
      fireEvent.click(docCardA);
      fireEvent.click(docCardB);

      // Verify execute button is enabled
      const executeBtn = screen.getByTestId("execute-comparison-btn");
      expect(executeBtn).not.toBeDisabled();

      // Click execute button
      fireEvent.click(executeBtn);

      // Expect ComparisonView to appear with table and narrative
      await waitFor(
        () => {
          expect(screen.getByTestId("comparison-view")).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByTestId("comparison-table-container")).toBeInTheDocument();
      expect(screen.getByTestId("comparison-narrative-section")).toBeInTheDocument();
      expect(screen.getByText(/Apple reported total revenue of \$412.00B/)).toBeInTheDocument();
    });

    it("handles API failure gracefully without crashing the workspace", async () => {
      server.use(
        http.post("*/api/v1/conversations/:id/query", () => {
          return HttpResponse.json(
            { detail: "Financial comparison engine unavailable" },
            { status: 500 }
          );
        })
      );

      useUiStore.setState({
        selectedDocumentIds: [mockDocument.id, mockDocumentB.id],
      });
      renderWithClient(<ComparePage />);

      await waitFor(() => {
        expect(screen.getByTestId("execute-comparison-btn")).not.toBeDisabled();
      });

      fireEvent.click(screen.getByTestId("execute-comparison-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("comparison-error-banner")).toBeInTheDocument();
      });
      expect(screen.getByTestId("comparison-error-banner")).toHaveTextContent(
        /Request failed with status 500|Comparison query failed/
      );
    });
  });

  // =========================================================================
  // 5. Cross-Page Integration Shortcuts
  // =========================================================================
  describe("Cross-Page Entry Points", () => {
    it("shows 'Compare Filings (N)' button in Documents page when 2+ filings are selected", async () => {
      useUiStore.setState({
        selectedDocumentIds: [mockDocument.id, mockDocumentB.id],
      });
      renderWithClient(<DocumentsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("compare-selected-docs-btn")).toBeInTheDocument();
      });
      expect(screen.getByTestId("compare-selected-docs-btn")).toHaveTextContent(
        "Compare Filings (2)"
      );
    });

    it("shows 'Compare' shortcut in Research page SelectedDocumentContext when 2+ filings are selected", async () => {
      useUiStore.setState({
        selectedDocumentIds: [mockDocument.id, mockDocumentB.id],
      });
      renderWithClient(<SelectedDocumentContext />);

      await waitFor(() => {
        expect(screen.getByTestId("research-compare-shortcut-btn")).toBeInTheDocument();
      });
      expect(screen.getByTestId("research-compare-shortcut-btn")).toHaveTextContent("Compare");
    });
  });
});
