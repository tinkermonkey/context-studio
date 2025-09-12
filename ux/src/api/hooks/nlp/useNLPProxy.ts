import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import {
  nlpService,
  ProxyStatusResponse,
  ProxyMonitoringResponse,
  ProxyConfiguration,
  ProxyConfigureResponse,
} from "@/api/services/nlp";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";

/**
 * Hook to get proxy status
 */
export const useNLPProxyStatus = (
  options?: UseQueryOptions<ProxyStatusResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP, "proxy-status"),
    queryFn: () => nlpService.getProxyStatus(),
    refetchInterval: 30 * 1000, // Refetch every 30 seconds
    staleTime: 15 * 1000, // 15 seconds
    ...options,
  });
};

/**
 * Hook to get proxy monitoring stats
 */
export const useNLPProxyMonitoring = (
  options?: UseQueryOptions<ProxyMonitoringResponse | null, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP, "proxy-monitoring"),
    queryFn: () => nlpService.getProxyMonitoring(),
    refetchInterval: 10 * 1000, // Refetch every 10 seconds
    staleTime: 5 * 1000, // 5 seconds
    enabled: true, // Always enabled to check if proxy is running
    ...options,
  });
};

/**
 * Hook to configure proxy settings
 */
export const useConfigureNLPProxy = (
  options?: UseMutationOptions<
    ProxyConfigureResponse,
    Error,
    ProxyConfiguration
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (config: ProxyConfiguration) =>
      nlpService.configureProxy(config),
    onSuccess: () => {
      // Invalidate proxy-related queries
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.NLP, "proxy-status"),
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.NLP, "proxy-monitoring"),
      });
    },
    onError: (error) => {
      console.error("Error configuring NLP proxy:", error);
    },
    ...options,
  });
};
