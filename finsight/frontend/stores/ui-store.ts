import { create } from "zustand";

interface UiState {
  sidebarOpen: boolean;
  citationDrawerOpen: boolean;
  activeCitationChunkId: string | null;
  selectedDocumentIds: string[];
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  openCitationDrawer: (chunkId: string) => void;
  closeCitationDrawer: () => void;
  setSelectedDocumentIds: (ids: string[]) => void;
  toggleDocumentSelection: (id: string) => void;
  clearDocumentSelection: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  citationDrawerOpen: false,
  activeCitationChunkId: null,
  selectedDocumentIds: [],

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  openCitationDrawer: (chunkId) =>
    set({ citationDrawerOpen: true, activeCitationChunkId: chunkId }),
  closeCitationDrawer: () =>
    set({ citationDrawerOpen: false, activeCitationChunkId: null }),

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
