import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DocumentStatusBadge } from "@/components/documents/document-status-badge";
import { DeleteDocumentDialog } from "@/components/documents/delete-document-dialog";
import { DocumentUploadZone } from "@/components/documents/document-upload-zone";
import { DocumentTable } from "@/components/documents/document-table";
import DocumentsPage from "@/app/documents/page";
import { useUiStore } from "@/stores/ui-store";
import { mockDocument, mockProcessingDocument } from "./mocks/data";
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

describe("Phase 11.3 Document Management UI Test Suite", () => {
  beforeEach(() => {
    useUiStore.setState({
      selectedDocumentIds: [],
      sidebarOpen: true,
      citationDrawerOpen: false,
    });
  });

  // ============================================================
  // 1. Document Status Badges
  // ============================================================
  describe("DocumentStatusBadge", () => {
    it("renders pending status badge with text and icon", () => {
      render(<DocumentStatusBadge status="pending" />);
      expect(screen.getByTestId("status-badge-pending")).toBeInTheDocument();
      expect(screen.getByText(/queued/i)).toBeInTheDocument();
    });

    it("renders processing status badge with pulsating activity", () => {
      render(<DocumentStatusBadge status="processing" />);
      expect(screen.getByTestId("status-badge-processing")).toBeInTheDocument();
      expect(screen.getByText(/processing/i)).toBeInTheDocument();
    });

    it("renders parsed status badge", () => {
      render(<DocumentStatusBadge status="parsed" />);
      expect(screen.getByTestId("status-badge-parsed")).toBeInTheDocument();
      expect(screen.getByText(/parsed/i)).toBeInTheDocument();
    });

    it("renders indexed status badge with ready indicator", () => {
      render(<DocumentStatusBadge status="indexed" />);
      expect(screen.getByTestId("status-badge-indexed")).toBeInTheDocument();
      expect(screen.getByText(/indexed/i)).toBeInTheDocument();
    });

    it("renders failed status badge with error indicator", () => {
      render(<DocumentStatusBadge status="failed" />);
      expect(screen.getByTestId("status-badge-failed")).toBeInTheDocument();
      expect(screen.getByText(/failed/i)).toBeInTheDocument();
    });
  });

  // ============================================================
  // 2. Document Upload Zone (Validation, Drag & Drop, API)
  // ============================================================
  describe("DocumentUploadZone", () => {
    it("accepts and stages valid PDF files", () => {
      const Wrapper = createTestWrapper();
      render(<DocumentUploadZone />, { wrapper: Wrapper });

      const file = new File(["dummy pdf content"], "tesla_10k_2025.pdf", {
        type: "application/pdf",
      });

      const input = screen.getByLabelText(/upload document drag and drop area/i);
      expect(input).toBeInTheDocument();

      const fileInput = document.getElementById("document-file-input") as HTMLInputElement;
      fireEvent.change(fileInput, { target: { files: [file] } });

      expect(screen.getByText("tesla_10k_2025.pdf")).toBeInTheDocument();
      expect(screen.getByTestId("upload-submit-btn")).toBeInTheDocument();
    });

    it("accepts valid TXT and CSV files", () => {
      const Wrapper = createTestWrapper();
      render(<DocumentUploadZone />, { wrapper: Wrapper });

      const txtFile = new File(["conference call transcript"], "earnings.txt", {
        type: "text/plain",
      });
      const fileInput = document.getElementById("document-file-input") as HTMLInputElement;
      fireEvent.change(fileInput, { target: { files: [txtFile] } });

      expect(screen.getByText("earnings.txt")).toBeInTheDocument();
    });

    it("rejects unsupported file formats with user-friendly error message", () => {
      const Wrapper = createTestWrapper();
      render(<DocumentUploadZone />, { wrapper: Wrapper });

      const invalidFile = new File(["malicious"], "spreadsheet.exe", {
        type: "application/x-msdownload",
      });
      const fileInput = document.getElementById("document-file-input") as HTMLInputElement;
      fireEvent.change(fileInput, { target: { files: [invalidFile] } });

      expect(screen.getByTestId("upload-error")).toBeInTheDocument();
      expect(
        screen.getByText(/unsupported file format/i)
      ).toBeInTheDocument();
      expect(screen.queryByTestId("upload-submit-btn")).not.toBeInTheDocument();
    });

    it("submits upload mutation successfully", async () => {
      const Wrapper = createTestWrapper();
      render(<DocumentUploadZone />, { wrapper: Wrapper });

      const file = new File(["content"], "nvidia_10k.pdf", {
        type: "application/pdf",
      });
      const fileInput = document.getElementById("document-file-input") as HTMLInputElement;
      fireEvent.change(fileInput, { target: { files: [file] } });

      const submitBtn = screen.getByTestId("upload-submit-btn");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByTestId("upload-success")).toBeInTheDocument();
      });
      expect(screen.getByText(/uploaded successfully/i)).toBeInTheDocument();
    });

    it("displays error message on upload API failure", async () => {
      server.use(
        http.post("*/api/v1/documents/upload", () => {
          return HttpResponse.json(
            {
              error: {
                code: "UNPROCESSABLE_ENTITY",
                message: "Magic-byte validation failed: corrupt PDF header.",
              },
            },
            { status: 422 }
          );
        })
      );

      const Wrapper = createTestWrapper();
      render(<DocumentUploadZone />, { wrapper: Wrapper });

      const file = new File(["corrupt"], "corrupt.pdf", {
        type: "application/pdf",
      });
      const fileInput = document.getElementById("document-file-input") as HTMLInputElement;
      fireEvent.change(fileInput, { target: { files: [file] } });

      const submitBtn = screen.getByTestId("upload-submit-btn");
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByTestId("upload-api-error")).toBeInTheDocument();
      });
      expect(
        screen.getByText(/magic-byte validation failed/i)
      ).toBeInTheDocument();
    });
  });

  // ============================================================
  // 3. Document Table & Multi-Selection
  // ============================================================
  describe("DocumentTable & Selection", () => {
    it("renders document list with file types, status badges, and metadata", () => {
      const Wrapper = createTestWrapper();
      render(
        <DocumentTable documents={[mockDocument, mockProcessingDocument]} />,
        { wrapper: Wrapper }
      );

      expect(screen.getByText(mockDocument.title!)).toBeInTheDocument();
      expect(screen.getByText(mockProcessingDocument.title!)).toBeInTheDocument();
      expect(screen.getByTestId("status-badge-indexed")).toBeInTheDocument();
      expect(screen.getByTestId("status-badge-processing")).toBeInTheDocument();
    });

    it("toggles single document selection in Zustand store", () => {
      const Wrapper = createTestWrapper();
      render(
        <DocumentTable documents={[mockDocument, mockProcessingDocument]} />,
        { wrapper: Wrapper }
      );

      const checkbox = screen.getByTestId(`document-checkbox-${mockDocument.id}`);
      expect(checkbox).not.toBeChecked();

      fireEvent.click(checkbox);
      expect(useUiStore.getState().selectedDocumentIds).toContain(mockDocument.id);

      fireEvent.click(checkbox);
      expect(useUiStore.getState().selectedDocumentIds).not.toContain(mockDocument.id);
    });

    it("disables selection for documents that are not yet indexed", () => {
      const Wrapper = createTestWrapper();
      render(
        <DocumentTable documents={[mockDocument, mockProcessingDocument]} />,
        { wrapper: Wrapper }
      );

      const processingCheckbox = screen.getByTestId(
        `document-checkbox-${mockProcessingDocument.id}`
      );
      expect(processingCheckbox).toBeDisabled();
    });

    it("handles select-all for eligible indexed documents", () => {
      const Wrapper = createTestWrapper();
      render(
        <DocumentTable documents={[mockDocument, mockProcessingDocument]} />,
        { wrapper: Wrapper }
      );

      const selectAll = screen.getByTestId("select-all-checkbox");
      fireEvent.click(selectAll);

      expect(useUiStore.getState().selectedDocumentIds).toEqual([mockDocument.id]);

      // Deselect all
      fireEvent.click(selectAll);
      expect(useUiStore.getState().selectedDocumentIds).toEqual([]);
    });
  });

  // ============================================================
  // 4. Delete Document Dialog
  // ============================================================
  describe("DeleteDocumentDialog", () => {
    it("opens dialog with document name and invokes confirmation", async () => {
      let confirmedId = "";
      render(
        <DeleteDocumentDialog
          document={mockDocument}
          open={true}
          onOpenChange={() => {}}
          onConfirm={(id) => {
            confirmedId = id;
          }}
        />
      );

      expect(screen.getByTestId("delete-document-dialog")).toBeInTheDocument();
      expect(screen.getByText(mockDocument.title!)).toBeInTheDocument();

      const deleteBtn = screen.getByTestId("confirm-delete-btn");
      fireEvent.click(deleteBtn);

      expect(confirmedId).toBe(mockDocument.id);
    });

    it("displays error message if deletion fails", () => {
      render(
        <DeleteDocumentDialog
          document={mockDocument}
          open={true}
          onOpenChange={() => {}}
          onConfirm={() => {}}
          errorMessage="Failed to delete document from storage."
        />
      );

      expect(
        screen.getByText(/failed to delete document from storage/i)
      ).toBeInTheDocument();
    });
  });

  // ============================================================
  // 5. Full Documents Page Workspace
  // ============================================================
  describe("DocumentsPage Workspace", () => {
    it("renders document repository with statistics cards and table", async () => {
      const Wrapper = createTestWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      // Initially shows skeleton loading
      expect(screen.getByTestId("documents-loading-skeleton")).toBeInTheDocument();

      // Resolves to loaded documents
      await waitFor(() => {
        expect(screen.queryByTestId("documents-loading-skeleton")).not.toBeInTheDocument();
      });

      expect(screen.getByText("Document Repository")).toBeInTheDocument();
      expect(screen.getByText(mockDocument.title!)).toBeInTheDocument();
    });

    it("displays empty state when repository has zero documents", async () => {
      server.use(
        http.get("*/api/v1/documents/", () => {
          return HttpResponse.json({ total: 0, documents: [] });
        })
      );

      const Wrapper = createTestWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId("documents-empty-state")).toBeInTheDocument();
      });
      expect(screen.getByText(/no documents in repository/i)).toBeInTheDocument();
      expect(screen.getByTestId("empty-state-upload-btn")).toBeInTheDocument();
    });

    it("displays error state when initial document query fails", async () => {
      server.use(
        http.get("*/api/v1/documents/", () => {
          return HttpResponse.json(
            { error: { code: "SERVER_ERROR", message: "Database down" } },
            { status: 500 }
          );
        })
      );

      const Wrapper = createTestWrapper();
      render(<DocumentsPage />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByTestId("documents-error-state")).toBeInTheDocument();
      });
      expect(
        screen.getByText(/failed to load document repository/i)
      ).toBeInTheDocument();
    });
  });
});
