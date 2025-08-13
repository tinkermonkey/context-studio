/**
 * NLP Mutation Hooks
 * 
 * React Query mutation hooks for natural language processing operations
 */

import { useMutation, UseMutationOptions } from '@tanstack/react-query';
import { nlpService, type NLPAnalysisResponse, type TokenData, type EntityData } from '../../services/nlp';

/**
 * Hook to analyze text using mutation pattern (for manual triggering)
 */
export const useAnalyzeTextMutation = (
  options?: UseMutationOptions<NLPAnalysisResponse, Error, string>
) => {
  return useMutation({
    mutationFn: (text: string) => nlpService.analyzeText(text),
    ...options,
  });
};

/**
 * Hook to extract tokens using mutation pattern (for manual triggering)
 */
export const useExtractTokensMutation = (
  options?: UseMutationOptions<TokenData[], Error, string>
) => {
  return useMutation({
    mutationFn: (text: string) => nlpService.extractTokens(text),
    ...options,
  });
};

/**
 * Hook to extract entities using mutation pattern (for manual triggering)
 */
export const useExtractEntitiesMutation = (
  options?: UseMutationOptions<EntityData[], Error, string>
) => {
  return useMutation({
    mutationFn: (text: string) => nlpService.extractEntities(text),
    ...options,
  });
};

/**
 * Hook to get comprehensive analysis using mutation pattern (for manual triggering)
 */
export const useComprehensiveAnalysisMutation = (
  options?: UseMutationOptions<NLPAnalysisResponse, Error, string>
) => {
  return useMutation({
    mutationFn: (text: string) => nlpService.getComprehensiveAnalysis(text),
    ...options,
  });
};
