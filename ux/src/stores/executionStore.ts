import { create } from "zustand";

interface ExecutionState {
  inFlightPipelineIds: Set<string>;
  startExecution: (pipelineId: string) => void;
  endExecution: (pipelineId: string) => void;
  hasRunningExecutions: () => boolean;
}

export const useExecutionStore = create<ExecutionState>((set, get) => ({
  inFlightPipelineIds: new Set(),
  startExecution: (pipelineId: string) => {
    set((state) => ({
      inFlightPipelineIds: new Set(state.inFlightPipelineIds).add(pipelineId),
    }));
  },
  endExecution: (pipelineId: string) => {
    set((state) => {
      const newSet = new Set(state.inFlightPipelineIds);
      newSet.delete(pipelineId);
      return { inFlightPipelineIds: newSet };
    });
  },
  hasRunningExecutions: () => {
    return get().inFlightPipelineIds.size > 0;
  },
}));
