# FinSight Phase 11.3 Document Management UI Architecture

## 1. Overview & Objectives

Phase 11.3 delivers the **Document Management UI** for the FinSight investment research copilot. It allows an analyst to manage their financial document repository directly from the web interface, upload corporate SEC filings (10-K, 10-Q, earnings transcripts, data tables in PDF, TXT, or CSV formats), monitor background ingestion and HNSW vector indexing progress in real-time, scope active documents for multi-agent research, and safely delete documents.

---

## 2. Component Architecture

```
frontend/
├── app/
│   ├── page.tsx                           # Main Dashboard with repository summary cards
│   ├── documents/
│   │   └── page.tsx                       # Full Document Repository Workspace
│   ├── research/
│   │   └── page.tsx                       # Placeholder for Phase 11.4
│   ├── reports/
│   │   └── page.tsx                       # Placeholder for Phase 11.7
│   └── compare/
│       └── page.tsx                       # Placeholder for Phase 11.8
├── components/
│   ├── layout/
│   │   ├── app-shell.tsx                  # Responsive layout offset shell
│   │   ├── sidebar.tsx                    # Institutional navigation sidebar with active context badge
│   │   └── placeholder-page.tsx           # Institutional placeholder for future workspaces
│   ├── documents/
│   │   ├── document-upload-zone.tsx       # Drag-and-drop, format validation, size checks
│   │   ├── document-table.tsx             # Table view with selection checkboxes and actions
│   │   ├── document-status-badge.tsx      # Dual-channel status indicators (queued, processing, indexed, failed)
│   │   └── delete-document-dialog.tsx     # Confirmation dialog with pending and error handling
│   └── ui/
│       └── checkbox.tsx                   # Accessible design system checkbox primitive
```

---

## 3. Key Functional Behaviors

### 3.1 Document Upload & Ingestion Validation
- **Formats Supported**: PDF (`application/pdf`), TXT (`text/plain`), CSV (`text/csv`, `application/vnd.ms-excel`).
- **Validation**: Strict client-side extension and MIME-type validation before initiating network requests. Rejects invalid binaries (e.g. `.exe`) with explicit analyst-friendly error alerts.
- **Size Bounds**: Enforces maximum file size limit of 50MB and rejects empty (0-byte) files.
- **Drag & Drop**: Native drag-and-drop zone with visual border highlights (`border-primary bg-primary/5`), alongside standard file picker support.
- **Title Optionality**: Allows analyst to specify an optional human-readable title (defaults automatically to the clean filename).

### 3.2 Processing Lifecycle & Polling UX
- Integrates seamlessly with Phase 11.2 `useDocuments()` TanStack Query hook.
- Automatically polls the backend every 2.5 seconds while any document is in `pending` or `processing` status.
- Transitions to idle state without browser reloads once all filings reach terminal status (`indexed` or `failed`).
- Real-time status indicators in `DocumentStatusBadge`:
  - `pending` → "Queued" (Clock icon, secondary neutral badge)
  - `processing` → "Processing" (Spinning loader, pulsating financeWarning badge)
  - `parsed` → "Parsed" (FileCheck icon, primary accent)
  - `indexed` → "Indexed" (CheckCircle2 icon, financePositive badge)
  - `failed` → "Failed" (AlertCircle icon, financeNegative badge)

### 3.3 Multi-Document Selection & Active Context
- Checkbox selection is coupled to Zustand `useUiStore` (`selectedDocumentIds`).
- Only `indexed` documents are selectable for research context (in-flight or failed documents have disabled checkboxes with clear visual cues).
- Provides "Select All" functionality across all visible indexed documents.
- Selected count is reflected dynamically in both the table summary, header action bar, and the persistent navigation sidebar footer ("Active Context: N docs").

### 3.4 Deletion Flow
- Deletion requires explicit confirmation via `DeleteDocumentDialog`.
- Shows filing title/filename and warns that chunk embeddings and parsed tables will be removed.
- Disables interaction and shows loading spinner during the mutation.
- Automatically invalidates `queryKeys.documents.all()` and purges the document ID from active selection upon completion.

---

## 4. Testing Strategy

Tested using Vitest 2.1 and React Testing Library against MSW (Mock Service Worker):
- **Document Status Badges**: Verified all 5 lifecycle statuses render correct text, icons, and CSS variants.
- **Upload Flow**: Verified valid PDF, TXT, CSV staging; verified rejection of unsupported formats; verified successful API mutation; verified error display on 422 validation failure.
- **Table & Multi-Selection**: Verified tabular rendering of sizes, dates, and chunk counts; single selection toggle in Zustand; disabled checkboxes for processing docs; select-all toggle.
- **Deletion Flow**: Verified dialog open, confirmation callback, error display on failure.
- **Workspace States**: Verified skeleton loading state, empty state when total=0, and error state when backend API is unreachable.
- **Total Test Count**: 58 passing tests across 5 test suites (19 new tests in `documents-ui.test.tsx`).
