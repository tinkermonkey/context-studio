import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { adminService } from "@/api/services/admin";

export function useBackgroundTasks() {
  return useQuery({
    queryKey: QUERY_KEYS.backgroundTasks,
    queryFn: () => adminService.getBackgroundTasks(),
  });
}
