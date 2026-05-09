import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type TaxonomyCreateRequest = components["schemas"]["TaxonomyCreateRequest"];
type TaxonomyUpdateRequest = components["schemas"]["TaxonomyUpdateRequest"];

export function useTaxonomies() {
  return useQuery({
    queryKey: QUERY_KEYS.taxonomies,
    queryFn: () => ontologyService.listTaxonomies(),
  });
}

export function useTaxonomy(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.taxonomy(id),
    queryFn: () => ontologyService.getTaxonomy(id),
    enabled: !!id,
  });
}

export function useCreateTaxonomy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TaxonomyCreateRequest) => ontologyService.createTaxonomy(data),
    onSuccess: (result) => {
      const currentData = queryClient.getQueryData<{ items: components["schemas"]["TaxonomyResponse"][] }>(QUERY_KEYS.taxonomies);
      if (currentData) {
        queryClient.setQueryData(QUERY_KEYS.taxonomies, {
          ...currentData,
          items: [result, ...currentData.items],
        });
      } else {
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.taxonomies });
      }
    },
  });
}

export function useUpdateTaxonomy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TaxonomyUpdateRequest }) =>
      ontologyService.updateTaxonomy(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.taxonomies });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.taxonomy(id) });
    },
  });
}

export function useDeleteTaxonomy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => ontologyService.deleteTaxonomy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.taxonomies });
    },
  });
}

export function usePublishDiffStats(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.taxonomy(id).concat("publish-diff"),
    queryFn: () => ontologyService.getPublishDiffStats(id),
    enabled: !!id,
  });
}

export function usePublishTaxonomy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, commitMessage }: { id: string; commitMessage: string }) =>
      ontologyService.publishTaxonomy(id, commitMessage),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.taxonomies });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.taxonomy(id) });
    },
  });
}
