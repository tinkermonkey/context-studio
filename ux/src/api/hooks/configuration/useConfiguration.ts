import { useQuery, useMutation, useQueryClient, UseQueryOptions } from "@tanstack/react-query";
import {
  configurationService,
  type ConfigurationResponse,
  type ConfigurationData,
  type ReferenceSourcesResponse,
  type ReferenceSourcesStatusResponse,
  type ReferenceSource
} from "@/api/services/configuration";

/**
 * Hook to get full configuration
 */
export function useConfiguration(
  options?: Omit<UseQueryOptions<ConfigurationResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["configuration"],
    queryFn: () => configurationService.getConfiguration(),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to get specific configuration value
 */
export function useConfigurationValue(
  path: string | undefined,
  options?: Omit<UseQueryOptions<any, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["configurationValue", path],
    queryFn: path ? () => configurationService.getConfigurationValue(path) : undefined,
    enabled: Boolean(path),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to get configuration schema
 */
export function useConfigurationSchema(
  options?: Omit<UseQueryOptions<any, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["configurationSchema"],
    queryFn: () => configurationService.getConfigurationSchema(),
    staleTime: 10 * 60 * 1000, // 10 minutes - schema changes rarely
    gcTime: 30 * 60 * 1000, // 30 minutes
    ...options,
  });
}

/**
 * Hook to validate configuration
 */
export function useValidateConfiguration(
  options?: Omit<UseQueryOptions<{ valid: boolean; errors: string[] }, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["validateConfiguration"],
    queryFn: () => configurationService.validateConfiguration(),
    staleTime: 1 * 60 * 1000, // 1 minute
    gcTime: 2 * 60 * 1000, // 2 minutes
    ...options,
  });
}

/**
 * Hook to get reference sources configuration
 */
export function useReferenceSourcesConfig(
  options?: Omit<UseQueryOptions<ReferenceSourcesResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["referenceSourcesConfig"],
    queryFn: () => configurationService.getReferenceSourcesConfig(),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to get reference sources status
 */
export function useReferenceSourcesStatus(
  options?: Omit<UseQueryOptions<ReferenceSourcesStatusResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["referenceSourcesStatus"],
    queryFn: () => configurationService.getReferenceSourcesStatus(),
    staleTime: 30 * 1000, // 30 seconds - status changes more frequently
    gcTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 60 * 1000, // Refetch every minute for status updates
    ...options,
  });
}

/**
 * Hook to get specific reference source configuration
 */
export function useReferenceSourceConfig(
  sourceName: string | undefined,
  options?: Omit<UseQueryOptions<ReferenceSource, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: ["referenceSourceConfig", sourceName],
    queryFn: sourceName ? () => configurationService.getReferenceSourceConfig(sourceName) : undefined,
    enabled: Boolean(sourceName),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Hook to update configuration value
 */
export function useUpdateConfigurationValue() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ path, value }: { path: string; value: any }) =>
      configurationService.updateConfigurationValue(path, value),
    onSuccess: (_, { path }) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ["configuration"] });
      queryClient.invalidateQueries({ queryKey: ["configurationValue", path] });
      queryClient.invalidateQueries({ queryKey: ["validateConfiguration"] });
    },
  });
}

/**
 * Hook to update reference source configuration
 */
export function useUpdateReferenceSourceConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ sourceName, path, value }: { sourceName: string; path: string; value: any }) =>
      configurationService.updateReferenceSourceConfig(sourceName, path, value),
    onSuccess: (_, { sourceName }) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ["referenceSourcesConfig"] });
      queryClient.invalidateQueries({ queryKey: ["referenceSourceConfig", sourceName] });
      queryClient.invalidateQueries({ queryKey: ["referenceSourcesStatus"] });
      queryClient.invalidateQueries({ queryKey: ["validateConfiguration"] });
    },
  });
}

/**
 * Hook to reload configuration
 */
export function useReloadConfiguration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => configurationService.reloadConfiguration(),
    onSuccess: () => {
      // Invalidate all configuration queries
      queryClient.invalidateQueries({ queryKey: ["configuration"] });
      queryClient.invalidateQueries({ queryKey: ["configurationValue"] });
      queryClient.invalidateQueries({ queryKey: ["referenceSourcesConfig"] });
      queryClient.invalidateQueries({ queryKey: ["referenceSourcesStatus"] });
      queryClient.invalidateQueries({ queryKey: ["validateConfiguration"] });
    },
  });
}

/**
 * Hook to reset configuration to defaults
 */
export function useResetConfiguration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => configurationService.resetConfiguration(),
    onSuccess: () => {
      // Invalidate all configuration queries
      queryClient.invalidateQueries({ queryKey: ["configuration"] });
      queryClient.invalidateQueries({ queryKey: ["configurationValue"] });
      queryClient.invalidateQueries({ queryKey: ["referenceSourcesConfig"] });
      queryClient.invalidateQueries({ queryKey: ["referenceSourcesStatus"] });
      queryClient.invalidateQueries({ queryKey: ["validateConfiguration"] });
    },
  });
}