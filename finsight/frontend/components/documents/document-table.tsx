"use client";

import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { DocumentStatusBadge } from "./document-status-badge";
import { DeleteDocumentDialog } from "./delete-document-dialog";
import {
  Trash2,
  FileText,
  Clock,
  Layers,
  FileSpreadsheet,
  AlertTriangle,
} from "lucide-react";
import { useUiStore } from "@/stores/ui-store";
import { useDeleteDocument } from "@/hooks/use-documents";
import type { DocumentResponse } from "@/types/api";

interface DocumentTableProps {
  documents: DocumentResponse[];
}

export function DocumentTable({ documents }: DocumentTableProps) {
  const [documentToDelete, setDocumentToDelete] = useState<DocumentResponse | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const selectedDocumentIds = useUiStore((state) => state.selectedDocumentIds);
  const toggleDocumentSelection = useUiStore((state) => state.toggleDocumentSelection);
  const setSelectedDocumentIds = useUiStore((state) => state.setSelectedDocumentIds);

  const { mutate: deleteDoc, isPending: isDeleting } = useDeleteDocument();

  // Documents eligible for research selection (indexed)
  const selectableDocs = documents.filter((d) => d.status === "indexed");
  const isAllSelectableSelected =
    selectableDocs.length > 0 &&
    selectableDocs.every((d) => selectedDocumentIds.includes(d.id));

  const handleToggleSelectAll = () => {
    if (isAllSelectableSelected) {
      // Deselect all
      const selectableIdSet = new Set(selectableDocs.map((d) => d.id));
      setSelectedDocumentIds(
        selectedDocumentIds.filter((id) => !selectableIdSet.has(id))
      );
    } else {
      // Select all selectable
      const merged = Array.from(
        new Set([...selectedDocumentIds, ...selectableDocs.map((d) => d.id)])
      );
      setSelectedDocumentIds(merged);
    }
  };

  const handleDeleteConfirm = async (documentId: string) => {
    setDeleteError(null);
    deleteDoc(documentId, {
      onSuccess: () => {
        // Remove from selection if present
        if (selectedDocumentIds.includes(documentId)) {
          toggleDocumentSelection(documentId);
        }
        setDocumentToDelete(null);
      },
      onError: (err) => {
        setDeleteError(err.message || "Failed to delete document.");
      },
    });
  };

  const getFileIcon = (fileType: string) => {
    const lower = fileType.toLowerCase();
    if (lower === "csv") {
      return <FileSpreadsheet className="h-4 w-4 text-primary" aria-hidden="true" />;
    }
    return <FileText className="h-4 w-4 text-primary" aria-hidden="true" />;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes >= 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    return `${(bytes / 1024).toFixed(0)} KB`;
  };

  const formatDate = (isoString: string): string => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <>
      <div className="rounded-lg border bg-card shadow-sm overflow-hidden" data-testid="document-table-container">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="w-[44px] px-3">
                <Checkbox
                  checked={isAllSelectableSelected}
                  onCheckedChange={handleToggleSelectAll}
                  aria-label="Select all indexed documents"
                  disabled={selectableDocs.length === 0}
                  data-testid="select-all-checkbox"
                />
              </TableHead>
              <TableHead className="min-w-[240px]">Document / Filing</TableHead>
              <TableHead className="w-[120px]">Type</TableHead>
              <TableHead className="w-[130px]">Status</TableHead>
              <TableHead className="w-[110px] text-right">Chunks / Pages</TableHead>
              <TableHead className="w-[110px] text-right">Size</TableHead>
              <TableHead className="w-[120px] text-right">Uploaded</TableHead>
              <TableHead className="w-[60px] text-right pr-4">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((doc) => {
              const isSelected = selectedDocumentIds.includes(doc.id);
              const isSelectable = doc.status === "indexed";

              return (
                <TableRow
                  key={doc.id}
                  className={`transition-colors ${
                    isSelected ? "bg-primary/5 hover:bg-primary/10" : ""
                  }`}
                  data-testid={`document-row-${doc.id}`}
                >
                  <TableCell className="px-3">
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => toggleDocumentSelection(doc.id)}
                      disabled={!isSelectable}
                      aria-label={`Select ${doc.title || doc.filename}`}
                      data-testid={`document-checkbox-${doc.id}`}
                    />
                  </TableCell>

                  <TableCell className="py-3">
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5 shrink-0">{getFileIcon(doc.file_type)}</div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-sm text-foreground truncate max-w-[320px] sm:max-w-[400px]">
                            {doc.title || doc.filename}
                          </p>
                          {doc.processing_error && (
                            <span
                              className="inline-flex items-center text-xs text-destructive font-normal"
                              title={doc.processing_error}
                            >
                              <AlertTriangle className="h-3 w-3 mr-0.5" />
                              Error
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate max-w-[320px]">
                          {doc.filename} {doc.source ? `• ${doc.source}` : ""}
                        </p>
                      </div>
                    </div>
                  </TableCell>

                  <TableCell className="text-xs uppercase text-muted-foreground font-mono">
                    {doc.file_type}
                  </TableCell>

                  <TableCell>
                    <DocumentStatusBadge status={doc.status} />
                  </TableCell>

                  <TableCell className="text-right text-xs text-muted-foreground font-tabular-nums">
                    {doc.total_chunks !== null ? (
                      <span className="inline-flex items-center gap-1 justify-end">
                        <Layers className="h-3 w-3 text-muted-foreground/70" />
                        {doc.total_chunks} chunks
                      </span>
                    ) : doc.total_pages !== null ? (
                      `${doc.total_pages} pp`
                    ) : (
                      "—"
                    )}
                  </TableCell>

                  <TableCell className="text-right text-xs text-muted-foreground font-tabular-nums">
                    {formatFileSize(doc.file_size)}
                  </TableCell>

                  <TableCell className="text-right text-xs text-muted-foreground">
                    {formatDate(doc.created_at)}
                  </TableCell>

                  <TableCell className="text-right pr-3">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                      onClick={() => {
                        setDeleteError(null);
                        setDocumentToDelete(doc);
                      }}
                      aria-label={`Delete ${doc.title || doc.filename}`}
                      data-testid={`delete-doc-btn-${doc.id}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <DeleteDocumentDialog
        document={documentToDelete}
        open={Boolean(documentToDelete)}
        onOpenChange={(open) => {
          if (!open) {
            setDocumentToDelete(null);
            setDeleteError(null);
          }
        }}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
        errorMessage={deleteError}
      />
    </>
  );
}
