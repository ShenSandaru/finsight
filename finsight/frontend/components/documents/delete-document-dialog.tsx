import React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, AlertTriangle } from "lucide-react";
import type { DocumentResponse } from "@/types/api";

interface DeleteDocumentDialogProps {
  document: DocumentResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (documentId: string) => Promise<void> | void;
  isDeleting?: boolean;
  errorMessage?: string | null;
}

export function DeleteDocumentDialog({
  document,
  open,
  onOpenChange,
  onConfirm,
  isDeleting = false,
  errorMessage = null,
}: DeleteDocumentDialogProps) {
  if (!document) return null;

  const handleConfirm = async () => {
    await onConfirm(document.id);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]" data-testid="delete-document-dialog">
        <DialogHeader className="gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
          </div>
          <DialogTitle className="text-base font-semibold">
            Delete document?
          </DialogTitle>
          <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
            Are you sure you want to delete{" "}
            <span className="font-semibold text-foreground">
              {document.title || document.filename}
            </span>
            ? This permanently removes the document, parsed tables, and vector chunk embeddings from the FinSight repository.
          </DialogDescription>
        </DialogHeader>

        {errorMessage && (
          <div
            className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive"
            role="alert"
          >
            {errorMessage}
          </div>
        )}

        <DialogFooter className="gap-2 pt-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={handleConfirm}
            disabled={isDeleting}
            className="gap-1.5"
            data-testid="confirm-delete-btn"
          >
            {isDeleting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                <span>Deleting...</span>
              </>
            ) : (
              <span>Delete Document</span>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
