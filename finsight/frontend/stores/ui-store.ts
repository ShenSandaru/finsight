import { create } from "zustand";

interface CitationContext {
  sourceNumber?: string | number | null;
  similarity?: number | null;
  statementType?: string | null;
  fiscalPeriods?: string[] | null;
}

interface UiState {
  sidebarOpen: boolean;
  citationDrawerOpen: boolean;
  activeCitationChunkId: string | null;
  activeCitationContext: CitationContext | null;
  selectedDocumentIds: string[];
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  openCitationDrawer: (chunkId: string, context?: CitationContext) => void;
  closeCitationDrawer: () => void;
  setSelectedDocumentIds: (ids: string[]) => void;
  toggleDocumentSelection: (id: string) => void;
  clearDocumentSelection: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  citationDrawerOpen: false,
  activeCitationChunkId: null,
  activeCitationContext: null,
  selectedDocumentIds: [],

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  openCitationDrawer: (chunkId, context) =>
    set({
      citationDrawerOpen: true,
      activeCitationChunkId: chunkId,
      activeCitationContext: context || null,
    }),
  closeCitationDrawer: () =>
    set({
      citationDrawerOpen: false,
      activeCitationChunkId: null,
      activeCitationContext: null,
    }),

  setSelectedDocumentIds: (ids) => set({ selectedDocumentIds: ids }),
  toggleDocumentSelection: (id) =>
    set((state) => {
      const exists = state.selectedDocumentIds.includes(id);
      return {
        selectedDocumentIds: exists
          ? state.selectedDocumentIds.filter((docId) => docId !== id)
          : [...state.selectedDocumentIds, id],
      };
    }),
  clearDocumentSelection: () => set({ selectedDocumentIds: [] }),
}));
