import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  modelCapabilitiesService,
  type SupportedModelsResponse,
  type ModelCapabilitiesResponse,
} from "@/api/services/modelCapabilities";

/**
 * Hook to get all supported models with optional provider filter
 */
export function useSupportedModels(
  provider?: string,
  options?: Omit<
    UseQueryOptions<SupportedModelsResponse, Error>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: ["supportedModels", provider],
    queryFn: () => modelCapabilitiesService.listSupportedModels(provider),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
}

/**
 * Hook to get supported models grouped by provider
 */
export function useSupportedModelsByProvider(
  options?: Omit<
    UseQueryOptions<Record<string, ModelCapabilitiesResponse[]>, Error>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: ["supportedModelsByProvider"],
    queryFn: () => modelCapabilitiesService.getModelsByProvider(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
}
