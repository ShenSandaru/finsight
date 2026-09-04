# FinSight — Phase 11.7 Structured Research Reports UI

## Overview

Phase 11.7 introduces the full frontend workflow for generating, tracking, viewing, and exporting **structured publication research reports** based on FinSight's existing asynchronous multi-agent DAG infrastructure.

The backend contract was maintained without any modifications, using the existing `/api/v1/reports` endpoints and Async ARQ worker pipeline.

---

## Architectural Highlights & Components

1. **Lifecycle Status Tracking (`ReportStatusBadge`)**:
   - Location: `frontend/components/reports/report-status-badge.tsx`
   - Accurately renders all 4 backend report states:
     - `pending`: Amber badge with clock icon
     - `processing`: Blue badge with animated spin loader
     - `completed`: Positive emerald badge with check circle
     - `failed`: Destructive rose badge with alert circle

2. **Report Generation Modal (`GenerateReportModal`)**:
   - Location: `frontend/components/reports/generate-report-modal.tsx`
   - Integrated into both the research chat workspace header (`/research`) and reports history page (`/reports`).
   - Supports:
     - Title configuration (optional)
     - Research inquiry / theme (validated 3–1000 characters)
     - Explicit document context scoping display synced with `useUiStore.selectedDocumentIds`
     - Automatic navigation to `/reports/[reportId]` upon submission.

3. **Deterministic Report Markdown Viewer (`ReportViewer`)**:
   - Location: `frontend/components/reports/report-viewer.tsx`
   - Deterministic Markdown renderer supporting:
     - Publication headings (`#`, `##`, `###`)
     - Publication financial tables with automatic right/center/left alignment and negative number highlighting
     - Unordered and bulleted evidence lists
     - Inline formatting: bold, italic, inline code snippets
     - Full citation integration: automatically translates `[SOURCE N]` tags into interactive `CitationPill` components connected to the Phase 11.5 `CitationDrawer`.

4. **Report Detail & Export View (`/reports/[reportId]`)**:
   - Location: `frontend/app/reports/[reportId]/page.tsx`
   - Live status polling via `useReport` with React Query.
   - Processing progress card while background DAG synthesizes findings.
   - Guardrails failure display if report generation fails.
   - Structured findings preview (`FindingList`) using Phase 11.6 components.
   - Full publication report viewer (`ReportViewer`).
   - One-click **Export Markdown** (`.md` file download) and **Copy Markdown** to clipboard.
   - Report deletion with confirmation dialog.

5. **Reports Management & History View (`/reports`)**:
   - Location: `frontend/app/reports/page.tsx`
   - Listing of all research reports with status filter tabs (`all`, `completed`, `processing`, `pending`, `failed`).
   - Live search input matching report titles and research queries.
   - Filing scope badges, timestamp formatting, and inline action controls.
   - Removed "Soon" badge from sidebar navigation item.

---

## Verification & Quality Assurance

- **Vitest Unit & Component Tests**:
  - `109 / 109` passing test suites (including 13 tests in `tests/reports-ui.test.tsx`).
- **TypeScript Typecheck**:
  - `npm run typecheck` passed with 0 errors.
- **ESLint**:
  - `npm run lint` passed with 0 warnings or errors.
- **Next.js Production Build**:
  - `npm run build` compiled cleanly (`/reports` and `/reports/[reportId]` pages statically/dynamically generated).
