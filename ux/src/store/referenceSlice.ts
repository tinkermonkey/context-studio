/**
 * Reference Store - Zustand slice for unified reference search state
 *
 * Manages search state, selected nodes, source preferences, and search history
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { UnifiedNode, UnifiedLink } from '@/api/types/unified';

export interface ReferenceState {
  // Search state
  searchResults: UnifiedNode[];
  totalResults: number;
  searchQuery: string;
  searchType: 'title' | 'definition';
  sourceErrors: Record<string, string>;
  isSearching: boolean;

  // Selection state
  selectedNode: UnifiedNode | null;
  nodeLinks: UnifiedLink[];

  // Preferences (persisted)
  selectedSources: string[];
  searchHistory: string[];
  recentNodes: UnifiedNode[];

  // UI state
  showSourceSelector: boolean;
  showNodeDetails: boolean;

  // Search actions
  setSearchResults: (results: UnifiedNode[], total: number) => void;
  setSearchQuery: (query: string) => void;
  setSearchType: (type: 'title' | 'definition') => void;
  setSourceErrors: (errors: Record<string, string>) => void;
  setIsSearching: (searching: boolean) => void;
  appendSearchResults: (results: UnifiedNode[], total: number) => void;

  // Selection actions
  selectNode: (node: UnifiedNode | null) => void;
  setNodeLinks: (links: UnifiedLink[]) => void;
  addToRecentNodes: (node: UnifiedNode) => void;

  // Source management
  toggleSource: (source: string) => void;
  setAllSources: (sources: string[]) => void;
  resetSources: () => void;

  // History management
  addToHistory: (query: string) => void;
  clearHistory: () => void;
  removeFromHistory: (query: string) => void;

  // UI actions
  toggleSourceSelector: () => void;
  setShowSourceSelector: (show: boolean) => void;
  setShowNodeDetails: (show: boolean) => void;

  // Utility actions
  clearSearch: () => void;
  clearAll: () => void;

  // Filter and sorting
  filterResultsBySource: (source: string) => UnifiedNode[];
  sortResultsByRelevance: () => void;
  sortResultsBySource: () => void;
}

const DEFAULT_SOURCES = ['conceptnet', 'wordnet', 'dbpedia', 'wikidata', 'schema_org'];
const MAX_HISTORY_ITEMS = 10;
const MAX_RECENT_NODES = 20;

export const useReferenceStore = create<ReferenceState>()(
  persist(
    (set, get) => ({
      // Initial state
      searchResults: [],
      totalResults: 0,
      searchQuery: '',
      searchType: 'title',
      sourceErrors: {},
      isSearching: false,
      selectedNode: null,
      nodeLinks: [],
      selectedSources: DEFAULT_SOURCES,
      searchHistory: [],
      recentNodes: [],
      showSourceSelector: false,
      showNodeDetails: false,

      // Search actions
      setSearchResults: (results, total) => set({
        searchResults: results,
        totalResults: total,
        isSearching: false,
      }),

      setSearchQuery: (query) => set({ searchQuery: query }),

      setSearchType: (type) => set({ searchType: type }),

      setSourceErrors: (errors) => set({ sourceErrors: errors }),

      setIsSearching: (searching) => set({ isSearching: searching }),

      appendSearchResults: (results, total) => set((state) => ({
        searchResults: [...state.searchResults, ...results],
        totalResults: total,
        isSearching: false,
      })),

      // Selection actions
      selectNode: (node) => set({
        selectedNode: node,
        nodeLinks: [], // Clear links when selecting new node
        showNodeDetails: !!node,
      }),

      setNodeLinks: (links) => set({ nodeLinks: links }),

      addToRecentNodes: (node) => set((state) => {
        const filtered = state.recentNodes.filter(n => n.id !== node.id);
        return {
          recentNodes: [node, ...filtered].slice(0, MAX_RECENT_NODES)
        };
      }),

      // Source management
      toggleSource: (source) => set((state) => ({
        selectedSources: state.selectedSources.includes(source)
          ? state.selectedSources.filter(s => s !== source)
          : [...state.selectedSources, source]
      })),

      setAllSources: (sources) => set({ selectedSources: sources }),

      resetSources: () => set({ selectedSources: DEFAULT_SOURCES }),

      // History management
      addToHistory: (query) => set((state) => {
        if (!query.trim() || state.searchHistory.includes(query)) {
          return state;
        }

        return {
          searchQuery: query,
          searchHistory: [
            query,
            ...state.searchHistory.filter(q => q !== query).slice(0, MAX_HISTORY_ITEMS - 1)
          ]
        };
      }),

      clearHistory: () => set({ searchHistory: [] }),

      removeFromHistory: (query) => set((state) => ({
        searchHistory: state.searchHistory.filter(q => q !== query)
      })),

      // UI actions
      toggleSourceSelector: () => set((state) => ({
        showSourceSelector: !state.showSourceSelector
      })),

      setShowSourceSelector: (show) => set({ showSourceSelector: show }),

      setShowNodeDetails: (show) => set({ showNodeDetails: show }),

      // Utility actions
      clearSearch: () => set({
        searchResults: [],
        totalResults: 0,
        searchQuery: '',
        sourceErrors: {},
        selectedNode: null,
        nodeLinks: [],
        isSearching: false,
        showNodeDetails: false,
      }),

      clearAll: () => set({
        searchResults: [],
        totalResults: 0,
        searchQuery: '',
        sourceErrors: {},
        selectedNode: null,
        nodeLinks: [],
        searchHistory: [],
        recentNodes: [],
        isSearching: false,
        showSourceSelector: false,
        showNodeDetails: false,
        selectedSources: DEFAULT_SOURCES,
      }),

      // Filter and sorting utilities
      filterResultsBySource: (source) => {
        const state = get();
        return state.searchResults.filter(result => result.source === source);
      },

      sortResultsByRelevance: () => set((state) => ({
        searchResults: [...state.searchResults].sort((a, b) =>
          b.confidence_score - a.confidence_score
        )
      })),

      sortResultsBySource: () => set((state) => ({
        searchResults: [...state.searchResults].sort((a, b) =>
          a.source.localeCompare(b.source)
        )
      })),
    }),
    {
      name: 'reference-storage',
      // Only persist user preferences, not search state
      partialize: (state) => ({
        selectedSources: state.selectedSources,
        searchHistory: state.searchHistory,
        recentNodes: state.recentNodes,
        searchType: state.searchType,
        showSourceSelector: state.showSourceSelector,
      }),
      version: 1, // For future migrations
    }
  )
);

// Selectors for commonly used derived state
export const useSearchState = () => {
  const store = useReferenceStore();
  return {
    query: store.searchQuery,
    results: store.searchResults,
    total: store.totalResults,
    type: store.searchType,
    isSearching: store.isSearching,
    hasResults: store.searchResults.length > 0,
    hasMore: store.searchResults.length < store.totalResults,
    errors: store.sourceErrors,
    hasErrors: Object.keys(store.sourceErrors).length > 0,
  };
};

export const useSelectionState = () => {
  const store = useReferenceStore();
  return {
    selectedNode: store.selectedNode,
    nodeLinks: store.nodeLinks,
    recentNodes: store.recentNodes,
    showDetails: store.showNodeDetails,
    hasSelection: !!store.selectedNode,
    hasLinks: store.nodeLinks.length > 0,
  };
};

export const useSourceState = () => {
  const store = useReferenceStore();
  return {
    selectedSources: store.selectedSources,
    allSelected: store.selectedSources.length === DEFAULT_SOURCES.length,
    noneSelected: store.selectedSources.length === 0,
    showSelector: store.showSourceSelector,
  };
};

export const useHistoryState = () => {
  const store = useReferenceStore();
  return {
    history: store.searchHistory,
    hasHistory: store.searchHistory.length > 0,
    recentNodes: store.recentNodes,
    hasRecentNodes: store.recentNodes.length > 0,
  };
};