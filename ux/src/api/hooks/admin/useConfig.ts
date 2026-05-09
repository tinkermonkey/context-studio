import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { adminService } from "@/api/services/admin";
import type { components } from "@/api/types";

type ConfigSectionUpdateRequest =
  components["schemas"]["ConfigSectionUpdateRequest"];

export function useConfig() {
  return useQuery({
    queryKey: QUERY_KEYS.config,
    queryFn: () => adminService.getConfig(),
  });
}

export function useUpdateConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      section,
      data,
    }: {
      section: string;
      data: ConfigSectionUpdateRequest;
    }) => adminService.updateConfigSection(section, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.config });
    },
  });
}
