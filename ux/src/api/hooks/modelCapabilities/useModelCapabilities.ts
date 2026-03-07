import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  modelCapabilitiesService,
  type ModelCapabilitiesResponse,
  type ModelCapabilities,
} from "@/api/services/modelCapabilities";

/**
 * Hook to get capabilities for a specific model
 */
export function useModelCapabilities(
  modelName: string | undefined,
  options?: Omit<
    UseQueryOptions<ModelCapabilitiesResponse, Error>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: ["modelCapabilities", modelName],
    queryFn: modelName
      ? () => modelCapabilitiesService.getModelCapabilities(modelName)
      : undefined,
    enabled: Boolean(modelName),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
}

/**
 * Hook to get typed capabilities for a specific model
 */
export function useTypedModelCapabilities(
  modelName: string | undefined,
  options?: Omit<
    UseQueryOptions<ModelCapabilities, Error>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: ["typedModelCapabilities", modelName],
    queryFn: modelName
      ? () => modelCapabilitiesService.getTypedModelCapabilities(modelName)
      : undefined,
    enabled: Boolean(modelName),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
}

/**
 * Hook to get models by specific provider
 */
export function useModelCapabilitiesByProvider(
  providerName: string | undefined,
  options?: Omit<
    UseQueryOptions<
      import("@/api/services/modelCapabilities").SupportedModelsResponse,
      Error
    >,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: ["modelCapabilitiesByProvider", providerName],
    queryFn: providerName
      ? () => modelCapabilitiesService.listModelsByProvider(providerName)
      : undefined,
    enabled: Boolean(providerName),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
}

/**
 * Hook to validate LLM configuration against model capabilities
 */
export function useValidateLLMConfig(
  modelName: string | undefined,
  config: {
    temperature?: number;
    top_p?: number;
    top_k?: number;
    max_tokens?: number;
    frequency_penalty?: number;
    presence_penalty?: number;
  },
  options?: Omit<UseQueryOptions<string[], Error>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: ["validateLLMConfig", modelName, config],
    queryFn: modelName
      ? () => modelCapabilitiesService.validateLLMConfig(modelName, config)
      : undefined,
    enabled: Boolean(modelName),
    staleTime: 30 * 1000, // 30 seconds (short for config validation)
    gcTime: 2 * 60 * 1000, // 2 minutes
    ...options,
  });
}
