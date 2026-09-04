# FinSight — Phase 11.5 Citation & Evidence Inspector Drawer

## Overview

In **Phase 11.5**, we implemented the **Citation & Evidence Inspector Drawer**, fulfilling the institutional research copilot principle:

> *"Every citation should lead the analyst back to inspectable source evidence."*

When an analyst clicks any grounded citation marker (e.g. `[SOURCE 1]`), FinSight slides open a dedicated institutional inspector displaying the exact, authoritative source chunk (narrative text or Markdown financial table) along with complete filing provenance, similarity relevance, and chunk classification.

---

## 1. Evidence Data Flow & Contract Audit

Prior to implementation, the citation and evidence lifecycle was traced end-to-end:

```text
User Query / Research Workspace
      ↓
POST /api/v1/conversations/{id}/query
      ↓
ConversationQueryResponse
      ├── answer: "Revenue increased to $412B [SOURCE 1]."
      └── citations: [
            {
              chunk_id: "33333333-...",
              document_id: "11111111-...",
              page_number: 28,
              chunk_type: "text",
              similarity: 0.892,
              statement_type: "income_statement",
              fiscal_periods: ["2025"]
            }
          ]
```

### Audit Findings & Path C Contract Decision
1. **Existing Citations**: Provided metadata (`chunk_id`, `document_id`, `page_number`, `chunk_type`, `similarity`, `statement_type`, `fiscal_periods`), but **omitted** the raw unedited `content` (chunk text or table Markdown).
2. **Database & ORM**: PostgreSQL pgvector table `chunks` already stores authoritative `content`, `chunk_type`, `chunk_index`, `page_number`, `metadata`, and foreign key relationship to `Document`.
3. **Endpoint Gap (Contract Decision Path C)**: There was no existing endpoint to retrieve a chunk by its `chunk_id`.
4. **Smallest Backend Footprint**:
   - Implemented `GET /api/v1/documents/chunks/{chunk_id}` in `backend/app/api/routes/documents.py`.
   - Added `ChunkNotFoundError(NotFoundError)` in `backend/app/core/exceptions.py`.
   - Added `DocumentChunkResponse` in `backend/app/schemas/document.py`.
   - Added `get_chunk(chunk_id: uuid.UUID)` in `backend/app/services/document_service.py` loading the parent `Document` relationship via `selectinload`.
   - Added comprehensive pytest unit/API tests in `backend/tests/test_chunk_endpoint.py`.

---

## 2. Architecture & State Management

### Separation of State
* **Zustand (`stores/ui-store.ts`)**:
  - Holds lightweight client UI state: `citationDrawerOpen: boolean`, `activeCitationChunkId: string | null`, and `activeCitationContext: CitationContext | null` (`sourceNumber`, `similarity`, `statementType`, `fiscalPeriods`).
* **TanStack Query (`hooks/use-documents.ts`)**:
  - `useCitationChunk(chunkId)`: Lazy-loaded query fetching `GET /api/v1/documents/chunks/{chunkId}` only when a valid `chunkId` is selected.
  - Cached for 5 minutes (`staleTime: 5 * 60 * 1000`) using centralized query key `queryKeys.documents.chunk(chunkId)`.

```text
Assistant Response Bubble
          │
      [SOURCE 1] (CitationPill)
          │
          ▼
  openCitationDrawer(chunkId, context) ──► Zustand Store (chunkId, sourceNumber)
                                                    │
                                                    ▼
                                          useCitationChunk(chunkId)
                                                    │
                                                    ▼
                                    GET /api/v1/documents/chunks/{chunkId}
                                                    │
                                                    ▼
                                            CitationDrawer
```

---

## 3. Component Design & Capabilities

### `frontend/components/citations/citation-drawer.tsx`

1. **Slide-Over Drawer Behavior**:
   - Built on Radix Dialog primitive (`@radix-ui/react-dialog`) with smooth slide-in-from-right animation and backdrop blur overlay.
   - Non-modal slide-over preserves research conversation context without navigation.
   - Supports keyboard `Escape` close, explicit `X` close control, and backdrop dismissal.

2. **Source Provenance Header**:
   - Institutional terminal aesthetic with `SOURCE N` pill badge.
   - Title: `Evidence Inspector`.
   - Subtitle: `Inspect authoritative filing provenance and underlying chunk evidence`.

3. **Document & Filing Metadata Card**:
   - Filing Document Title and original Filename.
   - Chunk Type Badge (`TEXT` with `FileText` icon vs `TABLE` with `Table` icon).
   - Provenance grid displaying `Page <N>`, `Relevance %` / cosine similarity, `Chunk Index`, and financial statement classification (e.g. *Income Statement*).
   - SEC / filing section info (e.g. *Item 7: MD&A*, table title, and reporting fiscal periods).

4. **Authoritative Evidence Presentation**:
   - **Text Evidence**: Selectable, unedited text viewer in a high-contrast readable container preserving verbatim wording and numbers.
   - **Table Evidence**: Built-in Markdown table parser rendering structured HTML `Table` (`TableHeader`, `TableRow`, `TableCell`) with horizontal scroll, alignment preservation (`:---`, `:---:`, `---:`), tabular numbers font, and automatic styling for negative/parenthetical values (e.g. `(45.12%)` in `text-finance-negative`).
   - Distinguishes retrieved source evidence from generated assistant analysis.

5. **Loading, Error & Unavailable States**:
   - **Loading**: Pulse skeletons matching the metadata card and evidence container layout.
   - **Error**: Institutional warning card with clean explanation and interactive **Retry** button invoking TanStack Query `refetch()`.
   - **Unavailable**: Graceful fallback indicator if an evidence chunk is missing.

---

## 4. Verification & Testing

### Frontend Test Coverage (`vitest` + RTL + MSW)
Created `frontend/tests/citation-drawer.test.tsx` covering:
* Closed state rendering.
* Opening drawer with `SOURCE N` badge and chunk ID.
* Close button interaction.
* Text evidence rendering with document title, page number, similarity, and section.
* Table evidence parsing and tabular HTML rendering with header/cell alignment.
* Citation pill click integration and switching between different source citations.
* Network 500 error state and Retry trigger.
* 404 not-found error handling.
* Accessibility attributes (`role="dialog"`, `aria-describedby`, close label).

### Backend Test Coverage (`pytest`)
Created `backend/tests/test_chunk_endpoint.py` covering:
* `get_chunk` service lookup with joined document title.
* Nonexistent chunk ID returning `None`.
* `GET /api/v1/documents/chunks/{chunk_id}` HTTP 200 response with exact content and metadata.
* `GET /api/v1/documents/chunks/{chunk_id}` HTTP 404 response for nonexistent chunk.
* HTTP 422 response for invalid/malformed UUIDs.

### Verification Results
* **Backend Pytest**: 5 passed (100%)
* **Frontend Tests**: 81 passed across 7 test suites (100%)
* **TypeScript Typecheck**: 0 errors (`tsc --noEmit`)
* **ESLint**: 0 warnings or errors (`next lint`)
* **Production Build**: 0 errors (`next build`, all 8 routes static prerendered)

---

## 5. Security Considerations
* **Strict Identifier Lookup**: Chunks are retrieved exclusively by validated UUID primary key against the database.
* **No Arbitrary Filesystem Traversal**: No endpoints expose raw server filesystem paths or file download handlers.
* **Database Isolation**: The backend acts as the sole authoritative source of truth.
