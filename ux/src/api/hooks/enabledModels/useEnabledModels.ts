import { useQuery, useMutation, useQueryClient, UseQueryOptions } from "@tanstack/react-query";
import {
  enabledModelsService,
  type EnabledModelsResponse,
  type EnabledModelConfig,
  type ProvidersStatusResponse,
  type ProviderType,
  type CostTier,
  type ModelCreateRequest,
  type ModelUpdateRequest
} from "@/api/services/enabledModels";

/**
 * Hook to list enabled models with optional filtering
 */
export function useEnabledModels(
  params?: {
    enabled_only?: boolean;
    provider_type?: ProviderType;
    tag?: string;
  },
  options?: Omit<UseQueryOptions<EnabledModelsResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["enabledModels", params],
    queryFn: () => enabledModelsService.listEnabledModels(params),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to get specific enabled model
 */
export function useEnabledModel(
  modelName: string | undefined,
  options?: Omit<UseQueryOptions<EnabledModelConfig, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["enabledModel", modelName],
    queryFn: modelName ? () => enabledModelsService.getEnabledModel(modelName) : undefined,
    enabled: Boolean(modelName),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to get providers status summary
 */
export function useProvidersStatus(
  options?: Omit<UseQueryOptions<ProvidersStatusResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["providersStatus"],
    queryFn: () => enabledModelsService.getProvidersStatus(),
    staleTime: 1 * 60 * 1000, // 1 minute
    gcTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 2 * 60 * 1000, // Refetch every 2 minutes
    ...options,
  });
}

/**
 * Hook to get models grouped by provider
 */
export function useModelsByProvider(
  options?: Omit<UseQueryOptions<Record<ProviderType, EnabledModelConfig[]>, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["modelsByProvider"],
    queryFn: () => enabledModelsService.getModelsByProvider(),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to get only enabled models
 */
export function useEnabledModelsOnly(
  options?: Omit<UseQueryOptions<EnabledModelConfig[], Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["enabledModelsOnly"],
    queryFn: () => enabledModelsService.getEnabledModelsOnly(),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to get models by tag
 */
export function useModelsByTag(
  tag: string | undefined,
  options?: Omit<UseQueryOptions<EnabledModelConfig[], Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["modelsByTag", tag],
    queryFn: tag ? () => enabledModelsService.getModelsByTag(tag) : undefined,
    enabled: Boolean(tag),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to get models by cost tier
 */
export function useModelsByCostTier(
  costTier: CostTier | undefined,
  options?: Omit<UseQueryOptions<EnabledModelConfig[], Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["modelsByCostTier", costTier],
    queryFn: costTier ? () => enabledModelsService.getModelsByCostTier(costTier) : undefined,
    enabled: Boolean(costTier),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to create new enabled model
 */
export function useCreateEnabledModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (config: ModelCreateRequest) => enabledModelsService.createEnabledModel(config),
    onSuccess: () => {
      // Invalidate all enabled models queries
      queryClient.invalidateQueries({ queryKey: ["enabledModels"] });
      queryClient.invalidateQueries({ queryKey: ["modelsByProvider"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModelsOnly"] });
      queryClient.invalidateQueries({ queryKey: ["providersStatus"] });
    },
  });
}

/**
 * Hook to update enabled model
 */
export function useUpdateEnabledModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ modelName, updates }: { modelName: string; updates: ModelUpdateRequest }) =>
      enabledModelsService.updateEnabledModel(modelName, updates),
    onSuccess: (_, { modelName }) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ["enabledModels"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModel", modelName] });
      queryClient.invalidateQueries({ queryKey: ["modelsByProvider"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModelsOnly"] });
      queryClient.invalidateQueries({ queryKey: ["providersStatus"] });
    },
  });
}

/**
 * Hook to delete enabled model
 */
export function useDeleteEnabledModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (modelName: string) => enabledModelsService.deleteEnabledModel(modelName),
    onSuccess: (_, modelName) => {
      // Invalidate and remove related queries
      queryClient.invalidateQueries({ queryKey: ["enabledModels"] });
      queryClient.removeQueries({ queryKey: ["enabledModel", modelName] });
      queryClient.invalidateQueries({ queryKey: ["modelsByProvider"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModelsOnly"] });
      queryClient.invalidateQueries({ queryKey: ["providersStatus"] });
    },
  });
}

/**
 * Hook to toggle model enabled state
 */
export function useToggleModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ modelName, enabled }: { modelName: string; enabled: boolean }) =>
      enabledModelsService.toggleModel(modelName, enabled),
    onSuccess: (_, { modelName }) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ["enabledModels"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModel", modelName] });
      queryClient.invalidateQueries({ queryKey: ["modelsByProvider"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModelsOnly"] });
      queryClient.invalidateQueries({ queryKey: ["providersStatus"] });
    },
  });
}

/**
 * Hook to enable a model
 */
export function useEnableModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (modelName: string) => enabledModelsService.enableModel(modelName),
    onSuccess: (_, modelName) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ["enabledModels"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModel", modelName] });
      queryClient.invalidateQueries({ queryKey: ["modelsByProvider"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModelsOnly"] });
      queryClient.invalidateQueries({ queryKey: ["providersStatus"] });
    },
  });
}

/**
 * Hook to disable a model
 */
export function useDisableModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (modelName: string) => enabledModelsService.disableModel(modelName),
    onSuccess: (_, modelName) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ["enabledModels"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModel", modelName] });
      queryClient.invalidateQueries({ queryKey: ["modelsByProvider"] });
      queryClient.invalidateQueries({ queryKey: ["enabledModelsOnly"] });
      queryClient.invalidateQueries({ queryKey: ["providersStatus"] });
    },
  });
}