# FinSight — Research Chat Workspace UI (Phase 11.4)

## Overview

Phase 11.4 transitions FinSight from a document management system into an interactive, multi-turn financial research workspace. The `/research` route provides an analyst-centric workspace integrating session navigation, multi-agent conversational RAG, contextual document scoping, and citation pill rendering.

---

## Architecture & Layout

The research workspace is organized within the institutional `AppShell`:

```text
┌────────────────────────────────────────────────────────────────────────────────┐
│ FinSight Navigation Sidebar                                                   │
├────────────────────────────┬───────────────────────────────────────────────────┤
│ Conversation Navigation    │ Research Workspace Header                         │
│ ┌────────────────────────┐ │ ┌───────────────────────────────────────────────┐ │
│ │ [+ New Research]       │ │ │ Apple FY2025 Margin Analysis                  │ │
│ ├────────────────────────┤ │ └───────────────────────────────────────────────┘ │
│ │ Active Sessions        │ │ Message Thread                                  │
│ │ • Apple FY25 Margin    │ │ ┌─────────────────────────────────────────────┐ │
│ │ • Microsoft Cloud ARR  │ │ │ [User] What was Apple's gross margin in '25?│ │
│ └────────────────────────┘ │ │                                               │ │
│                            │ │ [Assistant] Gross margin was 46.23% [SOURCE 1]│ │
│                            │ └─────────────────────────────────────────────┘ │
│                            │ Scoped Document Context                         │
│                            │ ┌─────────────────────────────────────────────┐ │
│                            │ │ Researching across: [AAPL 10-K] (1 filing)    │ │
│                            │ └─────────────────────────────────────────────┘ │
│                            │ Query Input                                     │
│                            │ ┌─────────────────────────────────────────────┐ │
│                            │ │ Ask about revenue, margins, cash flow...    │ │
│                            │ └─────────────────────────────────────────────┘ │
└────────────────────────────┴───────────────────────────────────────────────────┘
```

---

## Component Hierarchy

Located under `frontend/components/research/`:

1. **`conversation-sidebar.tsx`**:
   - Manages session navigation, displaying active and past sessions with message counts and dates.
   - Houses the `+ New Research` action and accessible delete confirmation dialog with `AlertDialog`.
2. **`message-thread.tsx`**:
   - Renders message stream, optimistic user queries, and analyst-friendly loading status ("Synthesizing financial evidence...").
   - Implements auto-scrolling with safe fallback for headless/JSDOM environments.
3. **`message-bubble.tsx`**:
   - Distinguishes user prompts from assistant research answers.
   - Regex-parses `[SOURCE N]` citation markers into clickable inline `CitationPill` components.
4. **`citation-pill.tsx`**:
   - Renders keyboard-accessible, mono-styled source tags.
   - Connects to `useUiStore.openCitationDrawer(chunkId)` (preparing for Phase 11.5).
5. **`selected-document-context.tsx`**:
   - Displays scoped document context badges from `useUiStore.selectedDocumentIds`.
   - Renders clear badge removal, "Clear" actions, and links to `/documents` for managing selections.
   - Explicitly displays "Researching across all repository filings (no filter)" when no documents are selected.
6. **`research-input.tsx`**:
   - Auto-resizing textarea supporting Enter to submit and Shift+Enter for newline.
   - Prevents empty/whitespace submissions and shows disabled/submitting states.
7. **`research-empty-state.tsx`**:
   - Context-aware empty states for:
     - No active research session (prompts analyst to create one).
     - Empty conversation (informs analyst on scope and invites initial inquiry).

---

## State Management Boundaries

- **Server State (TanStack Query)**:
  - Session metadata: `useConversationSession(sessionId)`
  - Message stream: `useConversationMessages(sessionId, limit)`
  - Mutation hooks: `useCreateSession`, `useDeleteSession`, `useConversationQuery(sessionId)`
  - Cache invalidation: Query responses trigger targeted invalidations on message history and session detail caches.
- **Client State (Zustand `useUiStore`)**:
  - `selectedDocumentIds`: Read to scope research queries (`document_ids` param) without storing conversational data in global client state.
  - `sidebarOpen`: Controls sidebar collapsing.
  - `citationDrawerOpen` / `activeCitationChunkId`: Connects citation pills to the upcoming Phase 11.5 drawer.

---

## Multi-Turn Query Flow

1. **Query Entry**: Analyst submits a query in `research-input.tsx`.
2. **Scoping**: `useUiStore.selectedDocumentIds` is inspected:
   - If populated, `document_ids` is included in the request.
   - If empty, `document_ids` is omitted, executing an unrestricted repository RAG query.
3. **Optimistic Rendering**: The user prompt is rendered immediately with an analyst loading indicator.
4. **API Execution**: `conversationsApi.querySession(sessionId, request)` is executed.
5. **Answer & Citations**:
   - Assistant message is appended with resolved answers.
   - `[SOURCE N]` tags are converted into `CitationPill` elements linked to retrieved chunk IDs.
6. **Conversational Memory**: Follow-up questions reuse the active session ID, allowing backend multi-turn context resolution.

---

## Verification & Testing

- **MSW Integration**: Deterministic handlers simulate session creation, session detail, message history, query submission, and deletion.
- **Automated Tests (`frontend/tests/research-ui.test.tsx`)**:
  - Citation pill rendering and store event triggering.
  - Assistant text parsing with inline citation replacement.
  - Research input submission, Enter/Shift+Enter behavior, and whitespace validation.
  - Conversation sidebar navigation, session selection, and delete confirmation dialog.
  - Scoped document context rendering and deselect/clear actions.
  - Full workspace query execution, optimistic loading states, and grounded response presentation.
  - API error handling with dismissible error bar.
- **Total Frontend Test Suite**: 71 tests passing across 6 suites (`api-client`, `foundation`, `domain-services`, `documents-ui`, `research-ui`, `query-hooks`).

---

## Phase 11.5 Boundary

Phase 11.4 implements citation pills that trigger `openCitationDrawer(chunkId)`. The full slide-over evidence inspector, chunk text rendering, metadata display, and financial table inspection drawer are deferred to **Phase 11.5 — Citation & Evidence Inspector Drawer**.
