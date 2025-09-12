/**
 * NLP Hooks
 *
 * React Query hooks for natural language processing operations
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  nlpService,
  type NLPAnalysisResponse,
  type TokenData,
  type EntityData,
} from "../../services/nlp";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to analyze text using NLP pipeline
 */
export const useNLPAnalysis = (
  text: string | null,
  options?: UseQueryOptions<NLPAnalysisResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP, "analysis", { text: text || "" }),
    queryFn: () => {
      if (!text) {
        throw new Error("Text is required for NLP analysis");
      }
      return nlpService.analyzeText(text);
    },
    enabled: !!text && text.trim().length > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes - NLP results are relatively stable
    gcTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
};

/**
 * Hook to extract tokens from text
 */
export const useTokenExtraction = (
  text: string | null,
  options?: UseQueryOptions<TokenData[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP, "tokens", { text: text || "" }),
    queryFn: () => {
      if (!text) {
        throw new Error("Text is required for token extraction");
      }
      return nlpService.extractTokens(text);
    },
    enabled: !!text && text.trim().length > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    ...options,
  });
};

/**
 * Hook to extract entities from text
 */
export const useEntityExtraction = (
  text: string | null,
  options?: UseQueryOptions<EntityData[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP, "entities", { text: text || "" }),
    queryFn: () => {
      if (!text) {
        throw new Error("Text is required for entity extraction");
      }
      return nlpService.extractEntities(text);
    },
    enabled: !!text && text.trim().length > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    ...options,
  });
};

/**
 * Hook to get comprehensive NLP analysis
 */
export const useComprehensiveNLPAnalysis = (
  text: string | null,
  options?: UseQueryOptions<NLPAnalysisResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP, "comprehensive", {
      text: text || "",
    }),
    queryFn: () => {
      if (!text) {
        throw new Error("Text is required for comprehensive NLP analysis");
      }
      return nlpService.getComprehensiveAnalysis(text);
    },
    enabled: !!text && text.trim().length > 0,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    ...options,
  });
};
