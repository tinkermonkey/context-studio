import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { adminService } from "@/api/services/admin";

export function useStatsTrends(days = 7) {
  return useQuery({
    queryKey: QUERY_KEYS.statsTrends(days),
    queryFn: () => adminService.getStatsTrends(days),
    staleTime: 5 * 60 * 1000, // 5 min
  });
}
