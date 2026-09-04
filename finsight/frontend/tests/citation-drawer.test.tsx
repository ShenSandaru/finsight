import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CitationDrawer } from "@/components/citations/citation-drawer";
import { CitationPill } from "@/components/research/citation-pill";
import { useUiStore } from "@/stores/ui-store";
import { mockTextChunk, mockTableChunk } from "./mocks/data";
import { server } from "./mocks/server";
import { http, HttpResponse } from "msw";

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("Phase 11.5 Citation & Evidence Inspector Drawer Test Suite", () => {
  beforeEach(() => {
    useUiStore.setState({
      citationDrawerOpen: false,
      activeCitationChunkId: null,
      activeCitationContext: null,
    });
  });

  // ============================================================
  // 1. Closed and Opening Behavior
  // ============================================================
  describe("Drawer State & Visibility", () => {
    it("does not render drawer content when closed", () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <CitationDrawer />
        </Wrapper>
      );

      expect(screen.queryByTestId("citation-drawer-content")).not.toBeInTheDocument();
    });

    it("opens drawer with correct source badge when openCitationDrawer is invoked", async () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <CitationDrawer />
        </Wrapper>
      );

      useUiStore.getState().openCitationDrawer(mockTextChunk.id, {
        sourceNumber: "3",
        similarity: 0.915,
      });

      await waitFor(() => {
        expect(screen.getByTestId("citation-drawer-content")).toBeInTheDocument();
      });

      expect(screen.getByTestId("citation-drawer-source-badge")).toHaveTextContent("SOURCE 3");
      expect(screen.getByText("Evidence Inspector")).toBeInTheDocument();
    });

    it("closes drawer when explicit close button is clicked", async () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <CitationDrawer />
        </Wrapper>
      );

      useUiStore.getState().openCitationDrawer(mockTextChunk.id, {
        sourceNumber: "1",
      });

      await waitFor(() => {
        expect(screen.getByTestId("citation-drawer-content")).toBeInTheDocument();
      });

      const closeButton = screen.getByTestId("citation-drawer-close-button");
      fireEvent.click(closeButton);

      expect(useUiStore.getState().citationDrawerOpen).toBe(false);
      expect(useUiStore.getState().activeCitationChunkId).toBeNull();
    });
  });

  // ============================================================
  // 2. Text Evidence & Metadata Rendering
  // ============================================================
  describe("Text Evidence Rendering", () => {
    it("displays authoritative text evidence, document metadata, page number, and TEXT badge", async () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <CitationDrawer />
        </Wrapper>
      );

      useUiStore.getState().openCitationDrawer(mockTextChunk.id, {
        sourceNumber: "1",
        similarity: 0.892,
      });

      await waitFor(() => {
        expect(screen.getByTestId("citation-doc-title")).toHaveTextContent(mockTextChunk.document_title!);
      });

      // Provenance chips
      expect(screen.getByTestId("citation-chunk-type-badge")).toHaveTextContent("TEXT");
      expect(screen.getByTestId("citation-page-number")).toHaveTextContent("Page 28");
      expect(screen.getByTestId("citation-similarity")).toHaveTextContent("89.2% (0.892)");

      // Text evidence content
      const textBlock = screen.getByTestId("citation-text-content");
      expect(textBlock).toBeInTheDocument();
      expect(textBlock).toHaveTextContent(
        "Total net sales were $412,000 million in fiscal year 2025, compared to $383,285 million in 2024."
      );

      // Section metadata
      expect(screen.getByText("Item 7. Management's Discussion and Analysis")).toBeInTheDocument();

      // Chunk ID traceability
      expect(screen.getByTestId("citation-chunk-id")).toHaveTextContent(`Chunk: ${mockTextChunk.id}`);
    });
  });

  // ============================================================
  // 3. Table Evidence Rendering
  // ============================================================
  describe("Table Evidence Rendering", () => {
    it("parses Markdown table structure and renders formatted HTML table with cells", async () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <CitationDrawer />
        </Wrapper>
      );

      useUiStore.getState().openCitationDrawer(mockTableChunk.id, {
        sourceNumber: "2",
        statementType: "income_statement",
      });

      await waitFor(() => {
        expect(screen.getByTestId("citation-table-container")).toBeInTheDocument();
      });

      // Chunk type badge
      expect(screen.getByTestId("citation-chunk-type-badge")).toHaveTextContent("TABLE");

      // Check table headers
      expect(screen.getByText("Line Item")).toBeInTheDocument();
      expect(screen.getByText("FY2025 ($M)")).toBeInTheDocument();
      expect(screen.getByText("FY2024 ($M)")).toBeInTheDocument();

      // Check table data rows
      expect(screen.getByText("Total Net Sales")).toBeInTheDocument();
      expect(screen.getByText("$412,000")).toBeInTheDocument();
      expect(screen.getByText("Cost of Sales")).toBeInTheDocument();
      expect(screen.getByText("Gross Margin %")).toBeInTheDocument();
      expect(screen.getByText("46.23%")).toBeInTheDocument();

      // Table metadata
      expect(screen.getByText("Consolidated Statements of Operations")).toBeInTheDocument();
      expect(screen.getByText("Periods: 2025, 2024")).toBeInTheDocument();
    });
  });

  // ============================================================
  // 4. Citation Pill to Drawer Integration
  // ============================================================
  describe("Citation Pill & Thread Integration", () => {
    it("clicking CitationPill opens the CitationDrawer with exact chunk ID and source metadata", async () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <div>
            <CitationPill
              sourceNumber="1"
              chunkId={mockTextChunk.id}
              similarity={0.92}
              statementType="income_statement"
            />
            <CitationDrawer />
          </div>
        </Wrapper>
      );

      const pill = screen.getByTestId("citation-pill-1");
      fireEvent.click(pill);

      expect(useUiStore.getState().citationDrawerOpen).toBe(true);
      expect(useUiStore.getState().activeCitationChunkId).toBe(mockTextChunk.id);

      await waitFor(() => {
        expect(screen.getByTestId("citation-text-content")).toBeInTheDocument();
      });
      expect(screen.getByTestId("citation-drawer-source-badge")).toHaveTextContent("SOURCE 1");
    });

    it("switching citation pill updates the drawer chunk", async () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <div>
            <CitationPill sourceNumber="1" chunkId={mockTextChunk.id} />
            <CitationPill sourceNumber="2" chunkId={mockTableChunk.id} />
            <CitationDrawer />
          </div>
        </Wrapper>
      );

      // Open source 1 (text)
      fireEvent.click(screen.getByTestId("citation-pill-1"));
      await waitFor(() => {
        expect(screen.getByTestId("citation-chunk-type-badge")).toHaveTextContent("TEXT");
      });

      // Switch to source 2 (table)
      fireEvent.click(screen.getByTestId("citation-pill-2"));
      await waitFor(() => {
        expect(screen.getByTestId("citation-chunk-type-badge")).toHaveTextContent("TABLE");
      });
      expect(screen.getByTestId("citation-table-container")).toBeInTheDocument();
    });
  });

  // ============================================================
  // 5. Error & Retry Handling
  // ============================================================
  describe("Error & Retry States", () => {
    it("displays error state when evidence chunk retrieval fails and supports retry", async () => {
      server.use(
        http.get("*/api/v1/documents/chunks/:id", () => {
          return HttpResponse.json(
            {
              error: {
                code: "INTERNAL_ERROR",
                message: "Internal server error retrieving chunk",
              },
            },
            { status: 500 }
          );
        })
      );

      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <CitationDrawer />
        </Wrapper>
      );

      useUiStore.getState().openCitationDrawer("failing-chunk-id", {
        sourceNumber: "4",
      });

      await waitFor(() => {
        expect(screen.getByTestId("citation-drawer-error")).toBeInTheDocument();
      });

      expect(screen.getByText("Unable to load source evidence")).toBeInTheDocument();
      expect(screen.getByTestId("citation-drawer-retry-button")).toBeInTheDocument();
    });

    it("displays clean not found message when chunk does not exist", async () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <CitationDrawer />
        </Wrapper>
      );

      useUiStore.getState().openCitationDrawer("not-found", {
        sourceNumber: "1",
      });

      await waitFor(() => {
        expect(screen.getByTestId("citation-drawer-error")).toBeInTheDocument();
      });
      expect(screen.getByText(/not found/i)).toBeInTheDocument();
    });
  });

  // ============================================================
  // 6. Accessibility & Keyboard Attributes
  // ============================================================
  describe("Accessibility", () => {
    it("has accessible dialog title, description, and close control", async () => {
      const Wrapper = createTestWrapper();
      render(
        <Wrapper>
          <CitationDrawer />
        </Wrapper>
      );

      useUiStore.getState().openCitationDrawer(mockTextChunk.id, {
        sourceNumber: "1",
      });

      await waitFor(() => {
        expect(screen.getByTestId("citation-drawer-content")).toBeInTheDocument();
      });

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeInTheDocument();

      const closeButton = screen.getByLabelText("Close evidence inspector");
      expect(closeButton).toBeInTheDocument();
    });
  });
});
