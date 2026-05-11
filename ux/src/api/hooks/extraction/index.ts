import { useMutation } from "@tanstack/react-query";
import { extractionService } from "@/api/services/extraction";
import type { components } from "@/api/types";

type EnrichFromReferencesRequest = components["schemas"]["EnrichFromReferencesRequest"];

export function useExtract() {
  return useMutation({
    mutationFn: (text: string) => extractionService.extract(text),
  });
}

export function useNlpAnalysis() {
  return useMutation({
    mutationFn: (text: string) => extractionService.analyzeText(text),
  });
}

export function useEnrichFromReferences() {
  return useMutation({
    mutationFn: (data: EnrichFromReferencesRequest) => extractionService.enrichFromReferences(data),
  });
}
