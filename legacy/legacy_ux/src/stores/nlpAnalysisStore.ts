import { create } from "zustand";

interface NlpAnalysisStore {
  // UI State
  currentText: string;
  shouldAnalyze: boolean;

  // Actions
  setText: (text: string) => void;
  triggerAnalysis: () => void;
  reset: () => void;
}

/**
 * Zustand store for coordinating NLP analysis UI state.
 *
 * This store manages when and what to analyze, while TanStack Query
 * handles the actual data fetching and caching.
 *
 * Usage:
 * - Call setText() and triggerAnalysis() from buttons/toolbars
 * - NlpAnalysisPanel watches shouldAnalyze to trigger refetch
 * - TanStack Query automatically caches results by text
 */
export const useNlpAnalysisStore = create<NlpAnalysisStore>((set) => ({
  currentText: "",
  shouldAnalyze: false,

  setText: (text: string) => set({ currentText: text }),

  triggerAnalysis: () => set({ shouldAnalyze: true }),

  reset: () => set({ shouldAnalyze: false, currentText: "" }),
}));
