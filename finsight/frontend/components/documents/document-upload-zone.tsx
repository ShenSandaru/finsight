"use client";

import React, { useState, useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  UploadCloud,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
} from "lucide-react";
import { useUploadDocument } from "@/hooks/use-documents";

const ACCEPTED_EXTENSIONS = [".pdf", ".txt", ".csv"];
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "text/plain",
  "text/csv",
  "application/vnd.ms-excel",
];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

interface DocumentUploadZoneProps {
  onUploadSuccess?: () => void;
  className?: string;
}

export function DocumentUploadZone({
  onUploadSuccess,
  className,
}: DocumentUploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const {
    mutate: uploadDocument,
    isPending: isUploading,
    error: uploadError,
    reset: resetMutation,
  } = useUploadDocument();

  const validateFile = (file: File): string | null => {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() || "");
    const isExtensionValid = ACCEPTED_EXTENSIONS.includes(ext);
    const isMimeValid = !file.type || ACCEPTED_MIME_TYPES.includes(file.type);

    if (!isExtensionValid && !isMimeValid) {
      return `Unsupported file format. Please upload a PDF, TXT, or CSV file.`;
    }

    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds the 50MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`;
    }

    if (file.size === 0) {
      return `The selected file is empty (0 bytes).`;
    }

    return null;
  };

  const handleSelectedFile = (file: File) => {
    setClientError(null);
    setUploadSuccess(false);
    resetMutation();

    const validationError = validateFile(file);
    if (validationError) {
      setClientError(validationError);
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    // Suggest a default clean title based on filename
    if (!title) {
      const baseName = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
      setTitle(baseName.charAt(0).toUpperCase() + baseName.slice(1));
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleSelectedFile(e.target.files[0]);
    }
  };

  const handleClearSelection = () => {
    setSelectedFile(null);
    setTitle("");
    setClientError(null);
    setUploadSuccess(false);
    resetMutation();
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setClientError(null);
    uploadDocument(
      {
        file: selectedFile,
        title: title.trim() || undefined,
      },
      {
        onSuccess: () => {
          setUploadSuccess(true);
          setSelectedFile(null);
          setTitle("");
          if (fileInputRef.current) {
            fileInputRef.current.value = "";
          }
          if (onUploadSuccess) {
            onUploadSuccess();
          }
          // Reset success alert after 4 seconds
          setTimeout(() => {
            setUploadSuccess(false);
          }, 4000);
        },
      }
    );
  };

  return (
    <Card className={className} data-testid="document-upload-zone">
      <CardContent className="p-5">
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.csv"
            onChange={handleFileInputChange}
            className="hidden"
            id="document-file-input"
            disabled={isUploading}
          />

          {!selectedFile ? (
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center rounded-lg border border-dashed p-6 text-center cursor-pointer transition-colors ${
                dragActive
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30"
              }`}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  fileInputRef.current?.click();
                }
              }}
              aria-label="Upload document drag and drop area"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary mb-3">
                <UploadCloud className="h-5 w-5" aria-hidden="true" />
              </div>
              <p className="text-sm font-medium text-foreground">
                <span className="text-primary hover:underline">Click to upload</span>{" "}
                or drag and drop
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                SEC 10-K, 10-Q, Transcripts or Data Tables (PDF, TXT, CSV up to 50MB)
              </p>
            </div>
          ) : (
            <div className="rounded-lg border bg-muted/20 p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-primary/10 text-primary">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate text-foreground">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {(selectedFile.size / 1024).toFixed(1)} KB •{" "}
                      {selectedFile.name.split(".").pop()?.toUpperCase()}
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  onClick={handleClearSelection}
                  disabled={isUploading}
                  aria-label="Remove selected file"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="document-title-input"
                  className="text-xs font-medium text-muted-foreground"
                >
                  Document Title (Optional)
                </label>
                <Input
                  id="document-title-input"
                  placeholder="e.g. Apple Inc. FY2025 Form 10-K"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={isUploading}
                  className="h-8 text-xs"
                />
              </div>

              <div className="flex justify-end pt-1">
                <Button
                  type="submit"
                  size="sm"
                  disabled={isUploading}
                  className="gap-1.5"
                  data-testid="upload-submit-btn"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                      <span>Ingesting filing...</span>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>Upload to Repository</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}

          {clientError && (
            <div
              className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive"
              role="alert"
              data-testid="upload-error"
            >
              <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{clientError}</span>
            </div>
          )}

          {uploadError && (
            <div
              className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive"
              role="alert"
              data-testid="upload-api-error"
            >
              <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{uploadError.message || "Failed to upload document."}</span>
            </div>
          )}

          {uploadSuccess && (
            <div
              className="flex items-center gap-2 rounded-md border border-finance-positive/30 bg-finance-positive/10 p-3 text-xs text-finance-positive"
              role="status"
              data-testid="upload-success"
            >
              <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>Document uploaded successfully and queued for background indexing.</span>
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
