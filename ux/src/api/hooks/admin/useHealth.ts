import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { adminService } from "@/api/services/admin";

export function useHealth() {
  return useQuery({
    queryKey: QUERY_KEYS.health,
    queryFn: () => adminService.getHealth(),
    refetchInterval: 30_000,
  });
}
